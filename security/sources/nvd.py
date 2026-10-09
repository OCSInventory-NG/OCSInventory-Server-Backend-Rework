"""
Windows and macOS vulnerabilities through the NVD CVE API: every CVE of a CPE
product, then the installed version compared with the configuration ranges
(as measured in cve-poc/cpe_cves.py).
"""

import re
import time

import requests
from django.conf import settings
from inventory.software_identity.normalizers.cpe import cpe_identifier, cpe_version
from security.models import METHOD_NVD_ALL_VERSIONS, METHOD_NVD_RANGE

TIMEOUT = 120
PAGE_SIZE = 2000
# NVD rate limits: 5 requests per 30 seconds without a key, 50 with one
SPACING = 6.5
SPACING_WITH_KEY = 0.7
_BOUNDS = (
    "versionStartIncluding",
    "versionStartExcluding",
    "versionEndIncluding",
    "versionEndExcluding",
)
_ESCAPED = re.compile(r"\\(.)")
_UNESCAPED_COLON = re.compile(r"(?<!\\):")


class RateLimited(Exception):
    """The NVD refused the request (403 or 429): stop until the next run."""


def http_get(url, params, headers):
    response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
    if response.status_code in (403, 429):
        raise RateLimited(f"NVD answered {response.status_code}")
    response.raise_for_status()
    return response.json()


class NvdClient:
    def __init__(self, get=http_get, sleep=time.sleep, api_key=None, base_url=None):
        self.get = get
        self.sleep = sleep
        self.api_key = settings.NVD_API_KEY if api_key is None else api_key
        self.base_url = base_url or settings.NVD_CVE_API_URL
        self.spacing = SPACING_WITH_KEY if self.api_key else SPACING
        self._requests = 0

    def product_cves(self, vendor_product):
        """Every CVE of a vendor:product, in compact form."""
        headers = {"apiKey": self.api_key} if self.api_key else {}
        cves, start = [], 0
        while True:
            if self._requests:
                self.sleep(self.spacing)
            self._requests += 1
            body = self.get(
                self.base_url,
                {
                    "virtualMatchString": cpe_identifier(vendor_product, ""),
                    "resultsPerPage": PAGE_SIZE,
                    "startIndex": start,
                },
                headers,
            )
            cves += [
                compact(item["cve"], vendor_product)
                for item in body.get("vulnerabilities", [])
            ]
            start += body.get("resultsPerPage", 0)
            if not body.get("resultsPerPage") or start >= body.get("totalResults", 0):
                return cves


def _unescape(value):
    return _ESCAPED.sub(r"\1", value)


def _cvss(metrics):
    """NVD's own score first, 3.1 then 3.0 then 4.0."""
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV40"):
        entries = metrics.get(key) or []
        if entries:
            entry = next(
                (e for e in entries if e.get("type") == "Primary"), entries[0]
            )
            data = entry.get("cvssData") or {}
            return (
                data.get("version", ""),
                data.get("vectorString", ""),
                data.get("baseScore"),
            )
    return "", "", None


def compact(cve, vendor_product):
    """What the findings need from an NVD CVE, for one vendor:product."""
    version, vector, score = _cvss(cve.get("metrics") or {})
    matches = []
    for configuration in cve.get("configurations") or []:
        for node in configuration.get("nodes") or []:
            for match in node.get("cpeMatch") or []:
                parts = _UNESCAPED_COLON.split(match.get("criteria", ""))
                if not match.get("vulnerable") or len(parts) < 6:
                    continue
                if _unescape(f"{parts[3]}:{parts[4]}") != vendor_product:
                    continue
                bounds = {b: match[b] for b in _BOUNDS if match.get(b)}
                matches.append({"criteria": match["criteria"], **bounds})
    description = next(
        (d["value"] for d in cve.get("descriptions") or [] if d.get("lang") == "en"),
        "",
    )
    return {
        "id": cve["id"],
        "published": cve.get("published", ""),
        "modified": cve.get("lastModified", ""),
        "description": description,
        "cvss_version": version,
        "cvss_vector": vector,
        "cvss_score": score,
        "matches": matches,
    }


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


def evaluate(cve, version):
    """
    How the installed version is affected by a compact CVE, None when it is
    not. A range or an exact version wins over an "all versions" entry.
    """
    installed = version or ""
    version = cpe_version(installed)
    all_versions = None
    for match in cve["matches"]:
        bounds = {bound: match[bound] for bound in _BOUNDS if match.get(bound)}
        parts = _UNESCAPED_COLON.split(match["criteria"])
        exact, update = _unescape(parts[5]), _unescape(parts[6])
        if bounds:
            if version and _within(version, bounds):
                return {
                    "method": METHOD_NVD_RANGE,
                    "fixed_version": bounds.get("versionEndExcluding", ""),
                    "affected_range": _words(bounds),
                    "uncertain": False,
                }
        elif exact not in ("*", "-"):
            # "9.0" with update "beta01" is that pre-release, not 9.0 itself
            pre_release = update not in ("*", "-", "")
            if (
                version
                and vcmp(exact, version) == 0
                and (not pre_release or update.lower() in installed.lower())
            ):
                return {
                    "method": METHOD_NVD_RANGE,
                    "fixed_version": "",
                    "affected_range": " ".join(
                        ["version", exact] + ([update] if pre_release else [])
                    ),
                    "uncertain": False,
                }
        elif exact == "*" and all_versions is None:
            all_versions = {
                "method": METHOD_NVD_ALL_VERSIONS,
                "fixed_version": "",
                "affected_range": "all versions",
                "uncertain": True,
            }
    return all_versions


def cve_url(cve_id):
    return f"https://nvd.nist.gov/vuln/detail/{cve_id}"
