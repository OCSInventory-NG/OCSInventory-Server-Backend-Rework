"""
Linux advisories from the OSV data dumps, one archive per ecosystem
(<base>/<ecosystem>/all.zip), loaded locally and compared by OCS.

Detection rests on the per CVE records (DEBIAN-CVE, UBUNTU-CVE), which also
carry the vulnerabilities without a fix, and on the Rocky, Alma and Red Hat
security advisories. DSA, DLA, USN, RHBA and RHEA are kept as references of
their CVEs only.
"""

import json
import logging
import re
import zipfile
from urllib.parse import quote, unquote

from django.db import transaction
from django.utils.dateparse import parse_datetime
from ocsinventory_backend.ocs_framework.progress import Progress
from security.models import (
    SOURCE_OSV_ALMA,
    SOURCE_OSV_DEBIAN,
    SOURCE_OSV_REDHAT,
    SOURCE_OSV_ROCKY,
    SOURCE_OSV_UBUNTU,
    OsvAdvisory,
    OsvAdvisoryCve,
    OsvAffected,
)

logger = logging.getLogger(__name__)

# Source: (OSV ecosystem of its archive, prefixes of its detection records;
# None: every record detects)
ARCHIVES = {
    SOURCE_OSV_DEBIAN: ("Debian", ("DEBIAN-CVE-",)),
    SOURCE_OSV_UBUNTU: ("Ubuntu", ("UBUNTU-CVE-",)),
    SOURCE_OSV_ROCKY: ("Rocky Linux", None),
    SOURCE_OSV_ALMA: ("AlmaLinux", None),
    SOURCE_OSV_REDHAT: ("Red Hat", ("RHSA-",)),
}
# purl namespace (distribution) of a source's packages
DISTRIBUTIONS = {
    "debian": SOURCE_OSV_DEBIAN,
    "ubuntu": SOURCE_OSV_UBUNTU,
    "rocky": SOURCE_OSV_ROCKY,
    "almalinux": SOURCE_OSV_ALMA,
    "redhat": SOURCE_OSV_REDHAT,
}
# os-release id of the machines of a purl namespace, when it differs
PLATFORM_IDS = {"redhat": "rhel"}
BATCH = 500
# Rows per INSERT: an Ubuntu advisory alone can carry hundreds of packages
WRITE_BATCH = 1000
# A new archive with less than this share of the advisories loaded is refused
MIN_SHARE = 0.5
_LTS = re.compile(r"^\d*[02468]\.04$")
# Rocky and Alma advisories start their summary with their severity
_SUMMARY_RATING = re.compile(r"^(Critical|Important|Moderate|Low):")
# Red Hat: RHEL itself (enterprise_linux), one ecosystem per repository on 8
# and 9 (enterprise_linux:9::appstream), per minor release from 10
# (enterprise_linux:10.1). The other products (JBoss, OpenShift...) and the
# extended streams of a minor release (rhel_eus, rhel_aus...) are left out.
_RHEL_ECOSYSTEM = re.compile(r"^Red Hat:enterprise_linux:(\d+)(\.\d+)?(::.*)?$")
_DEBUG_PACKAGE = re.compile(r"-debug(info|source)$")


def local_ecosystem(ecosystem, package):
    """
    The ecosystem an affected entry is kept under, None when it is not kept:
    Red Hat entries are kept per RHEL major release, without their debug
    packages, which no advisory is searched for.
    """
    if not ecosystem.startswith("Red Hat:"):
        return ecosystem
    match = _RHEL_ECOSYSTEM.match(ecosystem)
    if match is None or _DEBUG_PACKAGE.search(package):
        return None
    return f"Red Hat:enterprise_linux:{match.group(1)}"


def archive_url(base_url, source):
    ecosystem = ARCHIVES[source][0]
    return f"{base_url.rstrip('/')}/{quote(ecosystem)}/all.zip"


# Identities


def distribution(product):
    """The purl namespace of a Linux product (pkg:deb/debian/openssl), else ""."""
    if not product.startswith("pkg:"):
        return ""
    parts = product[4:].split("/")
    return parts[1] if len(parts) > 2 else ""


def source_of(product):
    """The OSV source that covers a purl product, None when none does."""
    return DISTRIBUTIONS.get(distribution(product))


def ecosystems(product, platform_key):
    """
    (standard, extended) OSV ecosystems of a Linux identity on its machine's
    platform; extended is the Ubuntu Pro ecosystem of an LTS release, else
    None. (None, None) when no source handles it: other distributions, or a
    package of another distribution than the machine's.
    """
    namespace = distribution(product)
    if ":" not in (platform_key or ""):
        return None, None
    distro, release = platform_key.split(":", 1)
    if PLATFORM_IDS.get(namespace, namespace) != distro or not release:
        return None, None
    if namespace == "debian":
        return f"Debian:{release}", None
    if namespace == "ubuntu":
        if _LTS.match(release):
            return f"Ubuntu:{release}:LTS", f"Ubuntu:Pro:{release}:LTS"
        return f"Ubuntu:{release}", None
    major = release.split(".")[0]
    if namespace == "rocky":
        return f"Rocky Linux:{major}", None
    if namespace == "almalinux":
        return f"AlmaLinux:{major}", None
    if namespace == "redhat":
        return f"Red Hat:enterprise_linux:{major}", None
    return None, None


def platform_source(platform_key):
    """
    (source, standard ecosystem) that cover a Linux platform's own packages,
    (None, None) when no source does.
    """
    distro = (platform_key or "").split(":")[0]
    namespace = next(
        (name for name, platform in PLATFORM_IDS.items() if platform == distro),
        distro,
    )
    source = DISTRIBUTIONS.get(namespace)
    if source is None:
        return None, None
    standard, _ = ecosystems(f"pkg:any/{namespace}/any", platform_key)
    return (source, standard) if standard else (None, None)


def package_name(product):
    """The source package of a purl product (pkg:deb/debian/libstdc%2B%2B6)."""
    return unquote(product.rsplit("/", 1)[1])


def query_name(product):
    """
    The package name of the advisories: signed kernel images are published
    under the kernel source (linux-signed-amd64 is linux, linux-signed-hwe-6.8
    is linux-hwe-6.8).
    """
    name = package_name(product)
    if not name.startswith("linux-signed"):
        return name
    rest = name[len("linux-signed") :]
    for arch in ("-amd64", "-arm64", "-i386"):
        if rest.startswith(arch):
            rest = rest[len(arch) :]
    return "linux" + rest


def advisory_url(advisory_id):
    return f"https://osv.dev/vulnerability/{advisory_id}"


# Records


def summary(record):
    """The summary, else the first line of the details (Debian records)."""
    text = record.get("summary") or (record.get("details") or "").split("\n")[0]
    return text.strip()[:500]


def compact(record, detection_prefixes):
    """What the local data keeps of an OSV record."""
    cves = []
    for alias in (record.get("aliases") or []) + (record.get("upstream") or []):
        if alias.startswith("CVE-") and alias not in cves:
            cves.append(alias)
    if record["id"].startswith("CVE-") and record["id"] not in cves:
        cves.append(record["id"])
    vectors = {
        severity.get("type"): severity.get("score")
        for severity in record.get("severity") or []
    }
    rating = vectors.get("Ubuntu", "")
    match = _SUMMARY_RATING.match(record.get("summary") or "")
    if not rating and match:
        rating = match.group(1)
    detection = detection_prefixes is None or record["id"].startswith(
        detection_prefixes
    )
    affected, kept = [], set()
    if detection:
        for entry in record.get("affected") or []:
            package = entry.get("package") or {}
            ecosystem = local_ecosystem(
                package.get("ecosystem", ""), package.get("name", "")
            )
            if ecosystem is None:
                continue
            ranges = [
                rng.get("events") or []
                for rng in entry.get("ranges") or []
                if rng.get("type") == "ECOSYSTEM"
            ]
            # Red Hat lists a package once per repository of its release
            same = (ecosystem, package.get("name", ""), json.dumps(ranges))
            if same in kept:
                continue
            kept.add(same)
            affected.append(
                {
                    "ecosystem": ecosystem,
                    "package": package.get("name", ""),
                    "ranges": ranges,
                    # The versions enumerated from the ranges: Debian and
                    # Ubuntu list every published one (95% of the Ubuntu
                    # archive), all inside the ranges. Kept without ranges only
                    "versions": [] if ranges else entry.get("versions") or [],
                    "urgency": (entry.get("ecosystem_specific") or {}).get(
                        "urgency", ""
                    ),
                }
            )
    vector = vectors.get("CVSS_V3") or vectors.get("CVSS_V4") or ""
    return {
        "id": record["id"],
        "detection": detection,
        "cves": cves,
        "summary": summary(record),
        "published": record.get("published", ""),
        "modified": record.get("modified", ""),
        "withdrawn": bool(record.get("withdrawn")),
        "vector": vector,
        "rating": rating,
        "affected": affected,
    }


def read_archive(path):
    """The records of an all.zip archive, one at a time."""
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith(".json"):
                yield json.loads(archive.read(name))


def _date(value):
    return parse_datetime(value) if value else None


def _write(source, records):
    ids = [record["id"] for record in records]
    with transaction.atomic():
        OsvAdvisory.objects.filter(advisory_id__in=ids).delete()
        advisories = OsvAdvisory.objects.bulk_create(
            (
                OsvAdvisory(
                    source=source,
                    advisory_id=record["id"],
                    detection=record["detection"],
                    cves=record["cves"],
                    summary=record["summary"],
                    published=_date(record["published"]),
                    modified=record["modified"],
                    withdrawn=record["withdrawn"],
                    cvss_vector=record["vector"][:255],
                    rating=record["rating"][:32],
                )
                for record in records
            ),
            batch_size=WRITE_BATCH,
        )
        # Read the ids back: bulk_create does not return them on every database
        pk = dict(
            OsvAdvisory.objects.filter(advisory_id__in=ids).values_list(
                "advisory_id", "id"
            )
        )
        del advisories
        OsvAdvisoryCve.objects.bulk_create(
            (
                OsvAdvisoryCve(advisory_id=pk[record["id"]], cve=cve)
                for record in records
                for cve in record["cves"]
            ),
            batch_size=WRITE_BATCH,
        )
        OsvAffected.objects.bulk_create(
            (
                OsvAffected(
                    advisory_id=pk[record["id"]],
                    ecosystem=entry["ecosystem"][:64],
                    package=entry["package"][:255],
                    ranges=entry["ranges"],
                    versions=entry["versions"],
                    urgency=entry["urgency"][:32],
                )
                for record in records
                for entry in record["affected"]
            ),
            batch_size=WRITE_BATCH,
        )


def load(source, path):
    """
    Loads an archive: advisories whose "modified" changed are written again,
    those gone from the archive are deleted once the whole archive was read.
    Returns (advisory count, {"ecosystems": [...]}).
    """
    prefixes = ARCHIVES[source][1]
    known = dict(
        OsvAdvisory.objects.filter(source=source).values_list("advisory_id", "modified")
    )
    seen, pending = set(), []
    read = Progress(logger, f"{source}: advisories read")
    for record in read_archive(path):
        if "id" not in record:
            continue
        read.advance()
        seen.add(record["id"])
        if record["id"] in known and known[record["id"]] == record.get("modified", ""):
            continue
        pending.append(compact(record, prefixes))
        if len(pending) >= BATCH:
            _write(source, pending)
            pending = []
    if known and len(seen) < MIN_SHARE * len(known):
        raise ValueError(
            f"{source}: {len(seen)} advisories against {len(known)} loaded,"
            " the archive is refused"
        )
    if pending:
        _write(source, pending)
    read.finish()
    gone = [advisory_id for advisory_id in known if advisory_id not in seen]
    for start in range(0, len(gone), BATCH):
        OsvAdvisory.objects.filter(advisory_id__in=gone[start : start + BATCH]).delete()
    found = sorted(
        set(
            OsvAffected.objects.filter(
                advisory__source=source, advisory__detection=True
            ).values_list("ecosystem", flat=True)
        )
    )
    return len(seen), {"ecosystems": found}
