"""
Linux vulnerabilities through the OSV API: querybatch by (ecosystem, source
package, full version), then the advisories. OSV compares dpkg and rpm
versions itself.
"""

import re
from urllib.parse import quote, unquote

import requests
from django.conf import settings

TIMEOUT = 60
BATCH_SIZE = 1000
_LTS = re.compile(r"^\d*[02468]\.04$")
# Rocky and Alma advisories start their summary with their severity
_SUMMARY_RATING = re.compile(r"^(Critical|Important|Moderate|Low):")


def http_post(url, payload):
    response = requests.post(url, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def http_get(url):
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def ecosystem(product, platform_key):
    """
    OSV ecosystem of a Linux identity (purl product and the machine's platform
    key), None when the maquette does not handle it: other distributions, or a
    package from another distribution than the machine's.
    """
    if not product.startswith("pkg:") or ":" not in (platform_key or ""):
        return None
    namespace = product[4:].split("/")[1]
    distro, release = platform_key.split(":", 1)
    if namespace != distro or not release:
        return None
    if namespace == "debian":
        return f"Debian:{release}"
    if namespace == "ubuntu":
        return f"Ubuntu:{release}:LTS" if _LTS.match(release) else f"Ubuntu:{release}"
    major = release.split(".")[0]
    if namespace == "rocky":
        return f"Rocky Linux:{major}"
    if namespace == "almalinux":
        return f"AlmaLinux:{major}"
    return None


def package_name(product):
    """The source package of a purl product (pkg:deb/debian/libstdc%2B%2B6)."""
    return unquote(product.rsplit("/", 1)[1])


def query_name(product):
    """
    The package name to ask OSV: signed kernel images are published under the
    kernel source (linux-signed-amd64 is linux, linux-signed-hwe-6.8 is
    linux-hwe-6.8).
    """
    name = package_name(product)
    if not name.startswith("linux-signed"):
        return name
    rest = name[len("linux-signed") :]
    for arch in ("-amd64", "-arm64", "-i386"):
        if rest.startswith(arch):
            rest = rest[len(arch) :]
    return "linux" + rest


class OsvClient:
    def __init__(self, post=http_post, get=http_get, base_url=None):
        self.post = post
        self.get = get
        self.base_url = (base_url or settings.OSV_API_URL).rstrip("/")

    def query(self, pairs):
        """
        {(ecosystem, name, version): [{"id", "modified"}]} for up to BATCH_SIZE
        pairs, following page tokens.
        """
        url = f"{self.base_url}/querybatch"
        answer = self.post(url, {"queries": [_query(pair) for pair in pairs]})
        results = {}
        for pair, result in zip(pairs, answer.get("results", [])):
            vulns = list(result.get("vulns") or [])
            token = result.get("next_page_token")
            while token:
                page = self.post(
                    url, {"queries": [{**_query(pair), "page_token": token}]}
                )["results"][0]
                vulns += page.get("vulns") or []
                token = page.get("next_page_token")
            results[pair] = vulns
        return results

    def advisory(self, advisory_id):
        return self.get(f"{self.base_url}/vulns/{quote(advisory_id, safe=':')}")


def _query(pair):
    eco, name, version = pair
    return {"package": {"name": name, "ecosystem": eco}, "version": version}


def summary(record):
    """The summary, else the first line of the details (Debian records)."""
    text = record.get("summary") or (record.get("details") or "").split("\n")[0]
    return text.strip()[:500]


def compact(record):
    """What the findings need from an OSV record."""
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

    return {
        "id": record["id"],
        "cves": cves,
        "published": record.get("published", ""),
        "modified": record.get("modified", ""),
        "vector": vectors.get("CVSS_V3") or vectors.get("CVSS_V4") or "",
        "rating": rating,
        "affected": [
            {
                "ecosystem": affected.get("package", {}).get("ecosystem", ""),
                "name": affected.get("package", {}).get("name", ""),
                "events": [
                    event
                    for rng in affected.get("ranges") or []
                    if rng.get("type") == "ECOSYSTEM"
                    for event in rng.get("events") or []
                ],
                "urgency": (affected.get("ecosystem_specific") or {}).get(
                    "urgency", ""
                ),
            }
            for affected in record.get("affected") or []
        ],
    }


def findings(compact_record, eco, name):
    """
    One finding per CVE of the advisory (its own id without CVE) for this
    package: fixed version, affected range in words, distribution rating.
    """
    entries = [
        affected
        for affected in compact_record["affected"]
        if affected["ecosystem"] == eco and affected["name"] == name
    ]
    events = [event for affected in entries for event in affected["events"]]
    fixed = [event["fixed"] for event in events if "fixed" in event]
    words = [f"{kind} {value}" for event in events for kind, value in event.items()]
    urgency = next(
        (affected["urgency"] for affected in entries if affected["urgency"]), ""
    )
    affected_range = ", ".join(words).replace("last_affected", "last affected")
    return [
        {
            "cve": cve,
            "fixed_version": ", ".join(fixed),
            "affected_range": affected_range,
            "rating": compact_record["rating"] or urgency,
        }
        for cve in compact_record["cves"] or [compact_record["id"]]
    ]


def advisory_url(advisory_id):
    return f"https://osv.dev/vulnerability/{advisory_id}"
