"""
Reading the findings: machines are found through the identity triple
(scheme, product, version), the dictionary and its machines, minus kernel
packages that are not the machine's running kernel. Computed per request:
fine at the maquette's scale, the full feature will need an aggregated table.
"""

from collections import Counter, defaultdict

from asset.inventory_base.models import InventoryBase
from django.db.models import Max
from inventory.software.models import AssetPlatform, SoftwareDictionary
from inventory.software_identity.models import SoftwareIdentity
from security.cvss import level
from security.kernel import is_kernel, is_running_kernel
from security.models import (
    METHOD_OSV,
    SOURCE_NVD,
    SOURCE_OSV,
    Finding,
    ProductCheck,
    Vulnerability,
)
from security.services import COVERED, nvd_version_key, osv_key
from security.sources import nvd, osv

LEVELS = ("critical", "high", "medium", "low", "unknown")
ORDERINGS = ("-cvss_score", "-machines")
PRODUCTS_SHOWN = 5


def _source(scheme, product):
    """The source package of a Linux identity, for the kernel rule."""
    return osv.package_name(product) if scheme == "purl" and product else ""


# When the running kernel's packages disagree, the least covered state wins
_KERNEL_PRIORITY = (
    "check_failed",
    "pending",
    "not_handled",
    "third_party",
    "no_origin",
    "no_identity",
    "not_supported",
    "checked",
)


class Installations:
    """Covered entries and the machines they count for, read once."""

    def __init__(self, asset_id=None):
        identities = SoftwareIdentity.objects.filter(
            status__in=COVERED["purl"] + COVERED["cpe"]
        ).values_list("entry_id", "scheme", "product", "version", "status")
        self.entries_of = defaultdict(list)
        self.status_of = {}
        self.source_of = {}
        for entry_id, scheme, product, version, status in identities:
            if status not in COVERED.get(scheme, ()):
                continue
            self.entries_of[(scheme, product, version)].append(entry_id)
            self.status_of[(scheme, product, version)] = status
            self.source_of[entry_id] = _source(scheme, product)
        entry_ids = [e for entries in self.entries_of.values() for e in entries]
        self.entries = {
            entry_id: (name, version, family)
            for entry_id, name, version, family in SoftwareDictionary.objects.filter(
                id__in=entry_ids
            ).values_list("id", "name", "version", "platform_family")
        }
        links = SoftwareDictionary.assets.through.objects.filter(
            softwaredictionary_id__in=entry_ids
        )
        if asset_id is not None:
            links = links.filter(inventorybase_id=asset_id)
        self.assets_of = defaultdict(set)
        for entry_id, asset in links.values_list(
            "softwaredictionary_id", "inventorybase_id"
        ):
            self.assets_of[entry_id].add(asset)
        self.running = dict(
            AssetPlatform.objects.values_list("asset_id", "running_kernel")
        )

    def counts(self, entry_id, asset):
        """Whether an installed entry counts for this machine (kernel rule)."""
        name, version, family = self.entries[entry_id]
        source = self.source_of.get(entry_id, "")
        if not is_kernel(name, family, source):
            return True
        running = self.running.get(asset, "")
        return is_running_kernel(name, version, family, running, source)

    def machines(self, triple):
        """The machines a finding of this identity triple counts for."""
        return {
            asset
            for entry_id in self.entries_of.get(triple, ())
            for asset in self.assets_of[entry_id]
            if self.counts(entry_id, asset)
        }

    def families(self, triple):
        return {self.entries[e][2] for e in self.entries_of.get(triple, ())}


def advisory_url(finding):
    if finding.method == METHOD_OSV:
        return osv.advisory_url(finding.advisory_id)
    return nvd.cve_url(finding.advisory_id)


def vulnerability_rows(
    level_filter=None, fix=None, family=None, asset_id=None, search="",
    ordering="-cvss_score",
):
    """One row per vulnerability that affects at least one machine."""
    installations = Installations(asset_id)
    search = (search or "").strip().lower()
    grouped = defaultdict(
        lambda: {"machines": set(), "products": [], "fixed": set(), "certain": False}
    )
    for finding in Finding.objects.values(
        "vulnerability_id", "scheme", "product", "version", "fixed_version",
        "uncertain",
    ):
        triple = (finding["scheme"], finding["product"], finding["version"])
        machines = installations.machines(triple)
        if not machines:
            continue
        if family and family not in installations.families(triple):
            continue
        group = grouped[finding["vulnerability_id"]]
        group["machines"] |= machines
        group["products"].append(
            {"product": finding["product"], "version": finding["version"]}
        )
        if finding["fixed_version"]:
            group["fixed"].add(finding["fixed_version"])
        group["certain"] |= not finding["uncertain"]

    rows = []
    for vuln in Vulnerability.objects.filter(id__in=grouped):
        group = grouped[vuln.id]
        products = sorted(group["products"], key=lambda p: (p["product"], p["version"]))
        row = {
            "vuln_id": vuln.vuln_id,
            "summary": vuln.summary,
            "cvss_score": vuln.cvss_score,
            "cvss_version": vuln.cvss_version,
            "level": level(vuln.cvss_score, vuln.distro_rating),
            "distro_rating": vuln.distro_rating,
            "source": vuln.source,
            "machines": len(group["machines"]),
            "products": products[:PRODUCTS_SHOWN],
            "product_count": len(products),
            "fix_available": bool(group["fixed"]),
            "fixed_versions": sorted(group["fixed"])[:PRODUCTS_SHOWN],
            "uncertain": not group["certain"],
        }
        if level_filter and row["level"] != level_filter:
            continue
        if fix is not None and row["fix_available"] != fix:
            continue
        if search and search not in vuln.vuln_id.lower() and not any(
            search in p["product"].lower() for p in products
        ):
            continue
        rows.append(row)

    def by_score(row):
        score = row["cvss_score"]
        return (score is None, -(score or 0), row["vuln_id"])

    if ordering == "-machines":
        rows.sort(key=lambda row: (-row["machines"], *by_score(row)))
    else:
        rows.sort(key=by_score)
    return rows


def vulnerability_detail(vuln):
    """The vulnerability, its findings, and the machines of each finding."""
    installations = Installations()
    findings = list(vuln.findings.all().order_by("product", "version"))
    asset_ids = set()
    machines_of = {}
    for finding in findings:
        triple = (finding.scheme, finding.product, finding.version)
        machines_of[finding.id] = installations.machines(triple)
        asset_ids |= machines_of[finding.id]
    assets = {
        asset_id: (name, last_update)
        for asset_id, name, last_update in InventoryBase.objects.filter(
            id__in=asset_ids
        ).values_list("id", "name", "last_update")
    }
    return {
        "vuln_id": vuln.vuln_id,
        "summary": vuln.summary,
        "published": vuln.published,
        "modified": vuln.modified,
        "cvss_version": vuln.cvss_version,
        "cvss_vector": vuln.cvss_vector,
        "cvss_score": vuln.cvss_score,
        "level": level(vuln.cvss_score, vuln.distro_rating),
        "distro_rating": vuln.distro_rating,
        "source": vuln.source,
        "url": vuln.url,
        "findings": [
            {
                "scheme": finding.scheme,
                "product": finding.product,
                "version": finding.version,
                "identity_status": installations.status_of.get(
                    (finding.scheme, finding.product, finding.version), ""
                ),
                "affected_range": finding.affected_range,
                "fixed_version": finding.fixed_version,
                "advisory_id": finding.advisory_id,
                "advisory_url": advisory_url(finding),
                "method": finding.method,
                "uncertain": finding.uncertain,
                "machines": sorted(
                    (
                        {
                            "id": asset_id,
                            "name": assets[asset_id][0],
                            "last_inventory": assets[asset_id][1],
                        }
                        for asset_id in machines_of[finding.id]
                    ),
                    key=lambda machine: machine["name"],
                ),
            }
            for finding in findings
        ],
    }


def _entry_state(identity, platform_key, checks):
    """Coverage state of a dictionary entry, from its identity and checks."""
    if identity is None:
        return "no_identity"
    status, reason, scheme, product, version = identity
    if status in ("review", "none"):
        return "no_identity"
    if status == "unsupported":
        return reason if reason in ("third_party", "no_origin") else "not_supported"
    if status not in COVERED.get(scheme, ()):
        return "not_supported"
    if scheme == "purl":
        eco = osv.ecosystem(product, platform_key)
        if eco is None:
            return "not_handled"
        key = (SOURCE_OSV, osv_key((eco, osv.query_name(product), version)))
        if key not in checks:
            return "pending"
        return "check_failed" if checks[key] else "checked"
    # NVD: the product's CVEs are fetched once, each version evaluated
    if checks.get((SOURCE_NVD, product)):
        return "check_failed"
    if (SOURCE_NVD, nvd_version_key(product, version)) in checks:
        return "checked"
    return "pending"


def coverage(asset_id=None):
    """
    What is checked and what is not, per platform family, over entries and
    installations; the machines per kernel status (or one machine's).
    """
    entries = SoftwareDictionary.objects.exclude(platform_family__isnull=True).exclude(
        platform_family=""
    )
    if asset_id is not None:
        entries = entries.filter(assets__id=asset_id)
    entries = {
        entry_id: (name, version, family, key)
        for entry_id, name, version, family, key in entries.values_list(
            "id", "name", "version", "platform_family", "platform_key"
        )
    }
    identities = {
        entry_id: rest
        for entry_id, *rest in SoftwareIdentity.objects.filter(
            entry_id__in=entries
        ).values_list("entry_id", "status", "reason", "scheme", "product", "version")
    }
    checks = {
        (source, key): bool(error)
        for source, key, error in ProductCheck.objects.values_list(
            "source", "key", "error"
        )
    }
    state = {
        entry_id: _entry_state(identities.get(entry_id), key, checks)
        for entry_id, (_, _, _, key) in entries.items()
    }
    links = SoftwareDictionary.assets.through.objects.filter(
        softwaredictionary_id__in=entries
    )
    if asset_id is not None:
        links = links.filter(inventorybase_id=asset_id)
    platforms = {
        asset: (family, running)
        for asset, family, running in AssetPlatform.objects.values_list(
            "asset_id", "family", "running_kernel"
        )
    }

    per_family = defaultdict(lambda: {"entries": Counter(), "installations": Counter()})
    for entry_id, (_, _, family, _) in entries.items():
        per_family[family]["entries"][state[entry_id]] += 1
    running_kernel_states = defaultdict(set)
    for entry_id, asset in links.values_list(
        "softwaredictionary_id", "inventorybase_id"
    ):
        name, version, family, _ = entries[entry_id]
        identity = identities.get(entry_id)
        source = _source(identity[2], identity[3]) if identity else ""
        installation = state[entry_id]
        if is_kernel(name, family, source):
            running = platforms.get(asset, ("", ""))[1]
            if is_running_kernel(name, version, family, running, source):
                running_kernel_states[asset].add(state[entry_id])
            else:
                installation = "kernel_not_running"
        per_family[family]["installations"][installation] += 1
    running_kernel_state = {
        asset: min(states, key=_KERNEL_PRIORITY.index)
        for asset, states in running_kernel_states.items()
    }

    linux_assets = [
        asset
        for asset, (family, _) in platforms.items()
        if family in ("deb", "rpm") and (asset_id is None or asset == asset_id)
    ]
    kernels = Counter(
        running_kernel_state.get(asset, "host_or_custom") for asset in linux_assets
    )
    result = {
        "families": [
            {
                "family": family,
                "entries": dict(counts["entries"]),
                "installations": dict(counts["installations"]),
            }
            for family, counts in sorted(per_family.items())
        ],
        "last_check": ProductCheck.objects.aggregate(last=Max("checked_at"))["last"],
    }
    if asset_id is None:
        result["kernels"] = dict(kernels)
    else:
        result["kernel"] = next(iter(kernels), "not_applicable")
        result["unchecked"] = sum(
            n
            for counts in per_family.values()
            for state_name, n in counts["installations"].items()
            if state_name != "checked"
        )
    return result
