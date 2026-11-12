"""
Windows and macOS vulnerabilities from the NVD yearly JSON 2.0 feeds
(nvdcve-2.0-<year>.json.gz), loaded locally: the years of the window with
their CPE matches, older years with their scores only.
"""

import gzip
import io
import json
import logging
import re
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from inventory.software_identity.normalizers.cpe import cpe_version
from ocsinventory_backend.ocs_framework.progress import Progress
from security.models import (
    METHOD_NVD_EXACT,
    METHOD_NVD_RANGE,
    NvdCve,
    NvdMatch,
)

logger = logging.getLogger(__name__)

FIRST_YEAR = 2002
BATCH = 2000
# Rows per INSERT: a CVE can carry thousands of CPE matches
WRITE_BATCH = 1000
# Years outside the window (scores only) are checked again after this
SCORE_YEARS_RECHECK = timedelta(days=7)
_BOUNDS = (
    "versionStartIncluding",
    "versionStartExcluding",
    "versionEndIncluding",
    "versionEndExcluding",
)
_ESCAPED = re.compile(r"\\(.)")
_UNESCAPED_COLON = re.compile(r"(?<!\\):")
_DECODER = json.JSONDecoder()


def window(years, today=None):
    """The years whose CVEs are loaded with their matches, the current one included."""
    current = (today or timezone.now()).year
    return list(range(current - max(years, 1) + 1, current + 1))


def cve_year(cve_id):
    parts = (cve_id or "").split("-")
    return int(parts[1]) if len(parts) > 2 and parts[1].isdigit() else 0


def cve_url(cve_id):
    return f"https://nvd.nist.gov/vuln/detail/{cve_id}"


def parse_meta(text):
    meta = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def iter_items(stream, key="vulnerabilities", chunk=1 << 20):
    """
    The items of the top level array `key` of a JSON document, decoded one at
    a time: a year of the NVD is several hundred MB of JSON.
    """
    buffer = ""
    position = 0
    eof = False

    def more():
        nonlocal buffer, position, eof
        data = stream.read(chunk)
        if not data:
            eof = True
            return False
        buffer = buffer[position:] + data
        position = 0
        return True

    marker = f'"{key}"'
    while True:
        found = buffer.find(marker, position)
        if found >= 0:
            position = found + len(marker)
            break
        position = max(0, len(buffer) - len(marker))
        if not more():
            return
    while True:
        bracket = buffer.find("[", position)
        if bracket >= 0:
            position = bracket + 1
            break
        position = len(buffer)
        if not more():
            return
    while True:
        while True:
            while position < len(buffer) and buffer[position] in " \t\r\n,":
                position += 1
            if position < len(buffer) or not more():
                break
        if position >= len(buffer) or buffer[position] == "]":
            return
        try:
            item, end = _DECODER.raw_decode(buffer, position)
        except json.JSONDecodeError:
            if eof or not more():
                raise
            continue
        position = end
        yield item


def _unescape(value):
    return _ESCAPED.sub(r"\1", value)


def _metric(metrics, keys):
    for key in keys:
        entries = metrics.get(key) or []
        if entries:
            entry = next((e for e in entries if e.get("type") == "Primary"), entries[0])
            data = entry.get("cvssData") or {}
            return data.get("vectorString", ""), data.get("baseScore")
    return "", None


def vendor_product(criteria):
    parts = _UNESCAPED_COLON.split(criteria or "")
    if len(parts) < 6:
        return ""
    return _unescape(f"{parts[3]}:{parts[4]}")


def cpe_part(criteria):
    """a (application), o (operating system) or h (hardware)."""
    parts = _UNESCAPED_COLON.split(criteria or "")
    return parts[2] if len(parts) > 2 else ""


def compact(cve):
    """What the local data keeps of an NVD CVE."""
    metrics = cve.get("metrics") or {}
    cvss3_vector, cvss3_score = _metric(metrics, ("cvssMetricV31", "cvssMetricV30"))
    cvss4_vector, cvss4_score = _metric(metrics, ("cvssMetricV40",))
    matches = []
    for configuration in cve.get("configurations") or []:
        nodes = configuration.get("nodes") or []
        # An AND with products that are not vulnerable: vulnerable with them
        # only. Operating systems name where; any other product is a
        # condition the inventory cannot check.
        conditions = (
            [
                match.get("criteria", "")
                for node in nodes
                for match in node.get("cpeMatch") or []
                if not match.get("vulnerable")
            ]
            if configuration.get("operator") == "AND"
            else []
        )
        systems = sorted(
            {vendor_product(c) for c in conditions if cpe_part(c) == "o"} - {""}
        )
        conditional = any(cpe_part(c) != "o" for c in conditions)
        for node in nodes:
            for match in node.get("cpeMatch") or []:
                if not match.get("vulnerable"):
                    continue
                product = vendor_product(match.get("criteria", ""))
                if not product:
                    continue
                matches.append(
                    {
                        "product": product,
                        "criteria": match["criteria"],
                        "bounds": {b: match[b] for b in _BOUNDS if match.get(b)},
                        "conditional": conditional,
                        "systems": systems,
                    }
                )
    description = next(
        (d["value"] for d in cve.get("descriptions") or [] if d.get("lang") == "en"),
        "",
    )
    return {
        "id": cve["id"],
        "published": cve.get("published", ""),
        "modified": cve.get("lastModified", ""),
        "rejected": cve.get("vulnStatus") == "Rejected",
        "description": description,
        "cvss3_vector": cvss3_vector,
        "cvss3_score": cvss3_score,
        "cvss4_vector": cvss4_vector,
        "cvss4_score": cvss4_score,
        "matches": matches,
    }


def _date(value):
    parsed = parse_datetime(value) if value else None
    if parsed is not None and timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _flush(year, full, cves):
    NvdCve.objects.bulk_create(
        (
            NvdCve(
                cve_id=cve["id"],
                year=year,
                full=full,
                rejected=cve["rejected"],
                published=_date(cve["published"]),
                modified=_date(cve["modified"]),
                description=cve["description"] if full else "",
                cvss3_vector=cve["cvss3_vector"][:255],
                cvss3_score=cve["cvss3_score"],
                cvss4_vector=cve["cvss4_vector"][:255],
                cvss4_score=cve["cvss4_score"],
            )
            for cve in cves
        ),
        batch_size=WRITE_BATCH,
    )
    if not full:
        return
    pk = dict(
        NvdCve.objects.filter(cve_id__in=[cve["id"] for cve in cves]).values_list(
            "cve_id", "id"
        )
    )
    NvdMatch.objects.bulk_create(
        (
            NvdMatch(
                cve_id=pk[cve["id"]],
                vendor_product=match["product"][:511],
                criteria=match["criteria"][:1024],
                bounds=match["bounds"],
                conditional=match["conditional"],
                systems=match["systems"],
            )
            for cve in cves
            for match in cve["matches"]
        ),
        batch_size=WRITE_BATCH,
    )


def load_year(year, path, full):
    """
    Replaces a year's CVEs from its gzip feed, in one transaction: a feed that
    fails to read leaves the year as it was. Returns the CVE count.
    """
    count = 0
    with transaction.atomic():
        NvdMatch.objects.filter(cve__year=year).delete()
        NvdCve.objects.filter(year=year).delete()
        with gzip.open(path, "rb") as raw:
            stream = io.TextIOWrapper(raw, encoding="utf-8")
            batch, seen = [], set()
            written = Progress(logger, f"NVD {year}: CVEs written")
            for item in iter_items(stream):
                cve = compact(item.get("cve") or {})
                if cve["id"] in seen or cve_year(cve["id"]) != year:
                    continue
                seen.add(cve["id"])
                batch.append(cve)
                if len(batch) >= BATCH:
                    _flush(year, full, batch)
                    count += len(batch)
                    written.advance(len(batch))
                    batch = []
            if batch:
                _flush(year, full, batch)
                count += len(batch)
                written.advance(len(batch))
            written.finish()
    return count


# Evaluation


def _vkey(version):
    """Natural ordering key: numbers numerically, other chunks lexically."""
    parts = re.findall(r"\d+|[a-zA-Z]+", version or "")
    return [(0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts]


def vcmp(a, b):
    ka, kb = _vkey(a), _vkey(b)
    length = max(len(ka), len(kb))
    ka += [(0, 0)] * (length - len(ka))
    kb += [(0, 0)] * (length - len(kb))
    return (ka > kb) - (ka < kb)


# Known mistakes of the NVD data, never reported: {CVE: why}
ERRATA = {
    "CVE-2024-20701": (
        "lists the SQL Server builds of the July 2024 security updates that fix"
        " it (15.0.2116.2, 15.0.4382.1) as the vulnerable ones"
    ),
}


def _major_digits(version):
    major = re.match(r"\d+", version or "")
    return len(major.group(0)) if major else 0


def same_numbering(version, bound):
    """
    Whether a bound counts versions like the installed version: a major of
    another order of magnitude is another numbering (Microsoft 365 Apps
    installed as 16.0.19127.20192, bounded by NVD as 2401.17231.20236).
    """
    return abs(_major_digits(version) - _major_digits(bound)) < 2


def _within(version, bounds):
    checks = {
        "versionStartIncluding": lambda bound: vcmp(version, bound) >= 0,
        "versionStartExcluding": lambda bound: vcmp(version, bound) > 0,
        "versionEndIncluding": lambda bound: vcmp(version, bound) <= 0,
        "versionEndExcluding": lambda bound: vcmp(version, bound) < 0,
    }
    return all(checks[name](bound) for name, bound in bounds.items())


def _words(bounds):
    words = []
    if "versionStartIncluding" in bounds:
        words.append(f"from {bounds['versionStartIncluding']}")
    if "versionStartExcluding" in bounds:
        words.append(f"after {bounds['versionStartExcluding']}")
    if "versionEndExcluding" in bounds:
        words.append(f"up to {bounds['versionEndExcluding']} excluded")
    if "versionEndIncluding" in bounds:
        words.append(f"up to {bounds['versionEndIncluding']} included")
    return " ".join(words)


# Operating systems named by the target_sw field of a CPE, and those each
# platform runs: a CPE for another system is not the installed software
# (FortiClient for macOS, Firefox for iOS). Other target_sw values name a
# runtime or a host application (node.js, wordpress) and never exclude.
OPERATING_SYSTEMS = {
    "windows",
    "macos",
    "mac_os",
    "mac_os_x",
    "os_x",
    "unix",
    "linux",
    "linux_kernel",
    "android",
    "iphone_os",
    "ipados",
    "ios",
    "chrome_os",
    "aix",
    "freebsd",
    "solaris",
    "esxi",
    "suse_linux_enterprise",
}
PLATFORM_SYSTEMS = {
    "windows": {"windows"},
    "macos": {"macos", "mac_os", "mac_os_x", "os_x", "unix"},
}
# The operating system CPEs (vendor:product) of a platform: Windows is named
# per edition too (microsoft:windows_10, microsoft:windows_server_2022)
_SYSTEM_CPES = {
    "windows": re.compile(r"^microsoft:windows(_.*)?$"),
    "macos": re.compile(r"^apple:(macos|mac_os|mac_os_x|os_x)$"),
}


def runs_on(systems, platform):
    """Whether the platform is one of the operating systems a CVE requires."""
    pattern = _SYSTEM_CPES.get(platform)
    return pattern is not None and any(pattern.match(s) for s in systems)


def for_platform(criteria, platform):
    """
    Whether a CPE criteria can describe software of this platform: its
    target_sw is any, not an operating system, or one the platform runs.
    An unknown platform keeps every criteria.
    """
    systems = PLATFORM_SYSTEMS.get(platform)
    if systems is None:
        return True
    parts = _UNESCAPED_COLON.split(criteria)
    target = _unescape(parts[10]).lower() if len(parts) > 10 else "*"
    return target not in OPERATING_SYSTEMS or target in systems


def evaluate(matches, installed, platform=""):
    """
    How an installed version is affected by the matches of one CVE, None when
    it is not or when it cannot be told for sure: only a range or an exact
    version count, never "all versions"; a match for another operating
    system than the platform's, or with a condition on another product, is
    skipped.
    """
    version = cpe_version(installed or "")
    for match in matches:
        bounds = match["bounds"]
        parts = _UNESCAPED_COLON.split(match["criteria"])
        if len(parts) < 7 or not for_platform(match["criteria"], platform):
            continue
        if match["conditional"]:
            continue
        if match.get("systems") and not runs_on(match["systems"], platform):
            continue
        exact, update = _unescape(parts[5]), _unescape(parts[6])
        if bounds:
            if not all(same_numbering(version, bound) for bound in bounds.values()):
                continue
            if version and _within(version, bounds):
                return {
                    "method": METHOD_NVD_RANGE,
                    "fixed_version": bounds.get("versionEndExcluding", ""),
                    "affected_range": _words(bounds),
                }
        elif exact not in ("*", "-"):
            # "9.0" with update "beta01" is that pre-release, not 9.0 itself
            pre_release = update not in ("*", "-", "")
            if (
                version
                and vcmp(exact, version) == 0
                and (not pre_release or update.lower() in (installed or "").lower())
            ):
                return {
                    "method": METHOD_NVD_EXACT,
                    "fixed_version": "",
                    "affected_range": " ".join(
                        ["version", exact] + ([update] if pre_release else [])
                    ),
                }
    return None
