"""
What the API shows: the open exposures grouped per vulnerability, ordered by
the priority criteria, exclusions applied; a machine's exposures and the
state of its software; the coverage of the fleet.
"""

from collections import Counter, defaultdict

from asset.inventory_base.models import InventoryBase
from django.db.models import Max
from security import config as security_config
from security.config import PRIORITY_CRITERIA
from security.cvss import level
from security.evaluation import Context
from security.exclusions import active_exclusions
from security.models import (
    METHOD_OSV,
    SOURCE_NVD,
    SOURCES,
    Exposure,
    OsvAdvisoryCve,
    ScanState,
    Vulnerability,
)
from security.scan import (
    CHECKED,
    EXCLUDED,
    KERNEL_NOT_RUNNING,
    STATES,
    Installations,
)
from security.sources import nvd, osv
from security.sync import NEVER_LOADED, source_state, source_syncs

LEVELS = ("critical", "high", "medium", "low", "unknown")
NOT_UNCHECKED = (CHECKED, EXCLUDED, KERNEL_NOT_RUNNING)
PRODUCTS_SHOWN = 5

# Findings faithful to their source but hidden by default (counted)
NOISE_KERNEL_UNFIXED = "kernel_unfixed"
NOISE = (NOISE_KERNEL_UNFIXED,)


# A machine as a whole: covered when the scan checks its own packages (Linux)
# or its software (Windows, macOS); otherwise, the first reason that applies
MACHINE_COVERED = "covered"
MACHINE_NOT_COVERED = "not_covered"
MACHINE_STATUSES = (MACHINE_COVERED, MACHINE_NOT_COVERED)
NO_PLATFORM = "no_platform"
NO_SOURCE = "no_source"
END_OF_SUPPORT = "end_of_support"
SOURCE_NEVER_LOADED = "source_never_loaded"
RELEASE_NOT_TRACKED = "release_not_tracked"
NOT_COVERED_REASONS = (
    NO_PLATFORM,
    NO_SOURCE,
    END_OF_SUPPORT,
    SOURCE_NEVER_LOADED,
    RELEASE_NOT_TRACKED,
)


def noise_of(exposure):
    """The noise category of an open exposure, "" when it is not noise."""
    if exposure["kernel"] and not exposure["fixed_version"]:
        return NOISE_KERNEL_UNFIXED
    return ""


def row_noise(categories):
    """
    The noise category of a vulnerability row: the one of all its detections
    shown, "" as soon as one of them is not noise.
    """
    if not categories or "" in categories:
        return ""
    return next(category for category in NOISE if category in categories)


def priority(ordering=None):
    """The active order: the given criteria, else the settings', first first."""
    if ordering:
        return list(ordering)
    configured = [
        c for c in security_config.current().priority if c in PRIORITY_CRITERIA
    ]
    return configured or list(PRIORITY_CRITERIA)


def _criterion(row, criterion):
    """Larger first, unknown last."""
    value = {
        "kev": row["kev"],
        "score": row["cvss_score"],
        "epss": row["epss"],
        "machines": row["machines"],
    }[criterion]
    if value is None:
        return (1, 0)
    return (0, -float(value))


def sort_rows(rows, order):
    rows.sort(
        key=lambda row: tuple(_criterion(row, c) for c in order) + (row["vuln_id"],)
    )
    return rows


def _rows(
    level_filter=None,
    fix=None,
    family=None,
    asset_id=None,
    search="",
    kev=None,
    show=(),
    now=None,
):
    """
    (rows, hidden counts): one row per vulnerability open on at least one
    machine, exclusions applied, noise hidden unless shown, filters applied;
    each row keeps the ids of its machines under "asset_ids".
    """
    exclusions = active_exclusions(now)
    exposures = Exposure.objects.filter(closed_at__isnull=True)
    if asset_id is not None:
        exposures = exposures.filter(asset_id=asset_id)
    if family:
        exposures = exposures.filter(platform_family=family)
    vuln_names = dict(
        Vulnerability.objects.filter(
            id__in=exposures.values("vulnerability_id")
        ).values_list("id", "vuln_id")
    )
    hidden = Counter()
    grouped = defaultdict(
        lambda: {
            "machines": set(),
            "products": {},
            "fixed": set(),
            "channels": set(),
            "certain": False,
            "methods": set(),
            "first_seen": None,
            "noise": set(),
        }
    )
    for exposure in exposures.values(
        "asset_id",
        "vulnerability_id",
        "product",
        "software_name",
        "version",
        "fixed_version",
        "fix_channel",
        "uncertain",
        "method",
        "rating",
        "kernel",
        "first_seen",
    ):
        vuln_id = vuln_names.get(exposure["vulnerability_id"], "")
        if exclusions.excludes(exposure["asset_id"], vuln_id):
            continue
        noise = noise_of(exposure)
        if noise and noise not in show:
            hidden[noise] += 1
            continue
        group = grouped[exposure["vulnerability_id"]]
        group["noise"].add(noise)
        group["machines"].add(exposure["asset_id"])
        group["products"][(exposure["product"], exposure["version"])] = exposure[
            "software_name"
        ]
        if exposure["fixed_version"]:
            group["fixed"].add(exposure["fixed_version"])
            group["channels"].add(exposure["fix_channel"])
        group["certain"] |= not exposure["uncertain"]
        group["methods"].add(exposure["method"])
        if group["first_seen"] is None or exposure["first_seen"] < group["first_seen"]:
            group["first_seen"] = exposure["first_seen"]

    search = (search or "").strip().lower()
    rows = []
    for vulnerability in Vulnerability.objects.filter(id__in=list(grouped)):
        group = grouped[vulnerability.id]
        products = sorted(
            (
                {"product": product, "version": version, "name": name}
                for (product, version), name in group["products"].items()
            ),
            key=lambda p: (p["product"], p["version"]),
        )
        row = {
            "vuln_id": vulnerability.vuln_id,
            "summary": vulnerability.summary,
            "kev": vulnerability.kev,
            "kev_date_added": vulnerability.kev_date_added,
            "cvss_score": vulnerability.cvss_score,
            "cvss_version": vulnerability.cvss_version,
            "epss": vulnerability.epss,
            "epss_percentile": vulnerability.epss_percentile,
            "level": level(vulnerability.cvss_score, vulnerability.distro_rating),
            "distro_rating": vulnerability.distro_rating,
            "source": "osv" if group["methods"] == {METHOD_OSV} else "nvd",
            "machines": len(group["machines"]),
            "products": products[:PRODUCTS_SHOWN],
            "product_count": len(products),
            "fix_available": bool(group["fixed"]),
            "fixed_versions": sorted(group["fixed"])[:PRODUCTS_SHOWN],
            "fix_channels": sorted(c or "standard" for c in group["channels"]),
            "uncertain": not group["certain"],
            "noise": row_noise(group["noise"]),
            "first_seen": group["first_seen"],
            "asset_ids": group["machines"],
        }
        if level_filter and row["level"] != level_filter:
            continue
        if fix is not None and row["fix_available"] != fix:
            continue
        if kev is not None and row["kev"] != kev:
            continue
        if (
            search
            and search not in vulnerability.vuln_id.lower()
            and not any(
                search in p["product"].lower() or search in (p["name"] or "").lower()
                for p in products
            )
        ):
            continue
        rows.append(row)
    return rows, dict(hidden)


def vulnerability_rows(ordering=None, **filters):
    """
    (rows, hidden counts, active order): the vulnerabilities shown by the
    list, in the active priority order. Filters as _rows.
    """
    rows, hidden = _rows(**filters)
    for row in rows:
        del row["asset_ids"]
    order = priority(ordering)
    return sort_rows(rows, order), hidden, order


def vulnerability_summary(**filters):
    """
    Totals of the vulnerabilities the list shows with the same filters: per
    level, exploited, with a fix, and the distinct machines impacted; the
    machines the scan does not cover, counted apart (machine and family
    filters only: the others select vulnerabilities, not machines).
    """
    rows, hidden = _rows(**filters)
    levels = Counter(row["level"] for row in rows)
    asset_id = filters.get("asset_id")
    machines = machine_rows(
        None if asset_id is None else [asset_id], filters.get("family")
    )
    return {
        "total": len(rows),
        "levels": {name: levels[name] for name in LEVELS},
        "kev": sum(1 for row in rows if row["kev"]),
        "fix_available": sum(1 for row in rows if row["fix_available"]),
        "machines": len(set().union(*(row["asset_ids"] for row in rows))),
        "hidden": hidden,
        "coverage": machine_counts(machines),
    }


def references(vulnerability):
    """The advisories that name the vulnerability, and its NVD page."""
    refs = [
        {"id": advisory_id, "url": osv.advisory_url(advisory_id), "source": source}
        for advisory_id, source in OsvAdvisoryCve.objects.filter(
            cve=vulnerability.vuln_id
        )
        .values_list("advisory__advisory_id", "advisory__source")
        .order_by("advisory__advisory_id")
    ]
    if vulnerability.vuln_id.startswith("CVE-"):
        refs.append(
            {
                "id": vulnerability.vuln_id,
                "url": nvd.cve_url(vulnerability.vuln_id),
                "source": "nvd",
            }
        )
    return refs


def _exposure_row(exposure, names, excluded):
    return {
        "asset": exposure.asset_id,
        "asset_name": names.get(exposure.asset_id, ""),
        "software_name": exposure.software_name,
        "scheme": exposure.scheme,
        "product": exposure.product,
        "version": exposure.version,
        "advisory_id": exposure.advisory_id,
        "advisory_url": (
            osv.advisory_url(exposure.advisory_id)
            if exposure.method == METHOD_OSV
            else nvd.cve_url(exposure.advisory_id)
        ),
        "fixed_version": exposure.fixed_version,
        "fix_channel": exposure.fix_channel or "standard",
        "method": exposure.method,
        "uncertain": exposure.uncertain,
        "rating": exposure.rating,
        "kernel": exposure.kernel,
        "first_seen": exposure.first_seen,
        "last_seen": exposure.last_seen,
        "closed_at": exposure.closed_at,
        "resolution": exposure.resolution,
        "excluded": excluded,
    }


def vulnerability_detail(vulnerability, now=None):
    exclusions = active_exclusions(now)
    exposures = list(
        Exposure.objects.filter(vulnerability=vulnerability).order_by(
            "closed_at", "asset_id", "product"
        )
    )
    names = dict(
        InventoryBase.objects.filter(
            id__in={e.asset_id for e in exposures}
        ).values_list("id", "name")
    )
    return {
        "vuln_id": vulnerability.vuln_id,
        "summary": vulnerability.summary,
        "published": vulnerability.published,
        "modified": vulnerability.modified,
        "cvss_version": vulnerability.cvss_version,
        "cvss_vector": vulnerability.cvss_vector,
        "cvss_score": vulnerability.cvss_score,
        "level": level(vulnerability.cvss_score, vulnerability.distro_rating),
        "distro_rating": vulnerability.distro_rating,
        "kev": vulnerability.kev,
        "kev_date_added": vulnerability.kev_date_added,
        "epss": vulnerability.epss,
        "epss_percentile": vulnerability.epss_percentile,
        "url": vulnerability.url,
        "references": references(vulnerability),
        "open": [
            _exposure_row(
                e, names, exclusions.excludes(e.asset_id, vulnerability.vuln_id)
            )
            for e in exposures
            if e.closed_at is None
        ],
        "closed": [
            _exposure_row(e, names, False) for e in exposures if e.closed_at is not None
        ],
    }


def asset_exposures(asset_id, status="open", now=None):
    """A machine's exposures, open or closed, exclusions marked."""
    exclusions = active_exclusions(now)
    exposures = Exposure.objects.filter(asset_id=asset_id).select_related(
        "vulnerability"
    )
    if status == "open":
        exposures = exposures.filter(closed_at__isnull=True)
    elif status == "closed":
        exposures = exposures.filter(closed_at__isnull=False)
    names = dict(InventoryBase.objects.filter(id=asset_id).values_list("id", "name"))
    rows = []
    for exposure in exposures:
        vulnerability = exposure.vulnerability
        row = _exposure_row(
            exposure,
            names,
            exclusions.excludes(asset_id, vulnerability.vuln_id),
        )
        row.update(
            {
                "vuln_id": vulnerability.vuln_id,
                "summary": vulnerability.summary,
                "cvss_score": vulnerability.cvss_score,
                "level": level(vulnerability.cvss_score, vulnerability.distro_rating),
                "kev": vulnerability.kev,
                "epss": vulnerability.epss,
                "noise": noise_of(
                    {
                        "rating": exposure.rating,
                        "kernel": exposure.kernel,
                        "fixed_version": exposure.fixed_version,
                    }
                ),
            }
        )
        rows.append(row)
    order = priority()
    for row in rows:
        row["machines"] = 1
    return sort_rows(rows, order)


def sources(now=None):
    """Each source's state: never loaded, stale or fresh, with its last runs."""
    syncs = source_syncs()
    return [
        {
            "source": source,
            "state": source_state(syncs[source], now),
            "last_attempt": syncs[source].last_attempt,
            "last_success": syncs[source].last_success,
            "data_changed_at": syncs[source].data_changed_at,
            "error": syncs[source].error,
            "record_count": syncs[source].record_count,
            "details": syncs[source].details,
        }
        for source in SOURCES
    ]


def machine_coverage(family, key, context):
    """
    (status, reason, support end) of a machine from its platform: reason ""
    when covered; support end, the date its release's security support ends
    (Linux), else None.
    """
    support_end = None
    if family in ("deb", "rpm") and ":" in key:
        base, _, release = key.partition(":")
        support_end = context.full_support_end.get((base, release))
    if family in ("windows", "macos"):
        if context.states[SOURCE_NVD] == NEVER_LOADED:
            return MACHINE_NOT_COVERED, SOURCE_NEVER_LOADED, None
        return MACHINE_COVERED, "", None
    if family not in ("deb", "rpm") or not key.partition(":")[2]:
        return MACHINE_NOT_COVERED, NO_PLATFORM, None
    source, ecosystem = osv.platform_source(key)
    if source is None:
        return MACHINE_NOT_COVERED, NO_SOURCE, support_end
    if context.past_support(key):
        return MACHINE_NOT_COVERED, END_OF_SUPPORT, support_end
    if context.states[source] == NEVER_LOADED:
        return MACHINE_NOT_COVERED, SOURCE_NEVER_LOADED, support_end
    if ecosystem not in context.ecosystems:
        return MACHINE_NOT_COVERED, RELEASE_NOT_TRACKED, support_end
    return MACHINE_COVERED, "", support_end


def machine_rows(asset_ids=None, family=None, now=None, context=None):
    """
    Each machine with its coverage, the machines not covered first. A machine
    without a resolved platform has family and platform "".
    """
    context = context or Context(now)
    assets = InventoryBase.objects.all()
    if asset_ids is not None:
        assets = assets.filter(id__in=asset_ids)
    if family:
        assets = assets.filter(platform__family=family)
    rows = []
    for asset_id, name, asset_family, key in assets.values_list(
        "id", "name", "platform__family", "platform__key"
    ):
        asset_family, key = asset_family or "", key or ""
        status, reason, support_end = machine_coverage(asset_family, key, context)
        rows.append(
            {
                "asset": asset_id,
                "name": name,
                "family": asset_family,
                "platform": key,
                "status": status,
                "reason": reason,
                "support_end": support_end,
            }
        )
    return sorted(
        rows,
        key=lambda row: (row["status"] != MACHINE_NOT_COVERED, row["name"]),
    )


def machine_counts(rows):
    """Machines covered and not covered, these per reason."""
    statuses = Counter(row["status"] for row in rows)
    reasons = Counter(row["reason"] for row in rows if row["reason"])
    return {
        MACHINE_COVERED: statuses[MACHINE_COVERED],
        MACHINE_NOT_COVERED: statuses[MACHINE_NOT_COVERED],
        "reasons": {reason: reasons[reason] for reason in NOT_COVERED_REASONS},
    }


def coverage(asset_id=None, now=None):
    """
    What is checked and what is not: installations per family and state (the
    first test that fails), running kernels per state, the sources.
    """
    context = Context(now)
    installations = Installations(context, None if asset_id is None else [asset_id])
    installations.load_evaluations()
    per_family = defaultdict(Counter)
    for asset, entry_ids in installations.entries_of.items():
        for entry_id in entry_ids:
            family = installations.entries[entry_id][2] or ""
            if not family:
                continue
            per_family[family][installations.state(entry_id, asset)] += 1
    linux_assets = [
        asset
        for asset, (family, _, _) in installations.platforms.items()
        if family in ("deb", "rpm")
    ]
    kernels = Counter(installations.running_kernel_state(a) for a in linux_assets)
    state = ScanState.objects.order_by("id").first()
    result = {
        "states": list(STATES),
        "families": [
            {"family": family, "installations": dict(counts)}
            for family, counts in sorted(per_family.items())
        ],
        "sources": sources(now),
        "last_full_scan": state.last_full_scan if state else None,
        "last_incremental_scan": state.last_incremental_scan if state else None,
        "last_exposure": Exposure.objects.aggregate(last=Max("last_seen"))["last"],
    }
    totals = Counter()
    for counts in per_family.values():
        totals.update(counts)
    # Not checked: every state but checked, the excluded machines (left out
    # on purpose, counted apart) and the kernels not running (out of scope)
    result["unchecked"] = sum(
        n for state_name, n in totals.items() if state_name not in NOT_UNCHECKED
    )
    result["excluded"] = totals.get(EXCLUDED, 0)
    machines = machine_rows(
        None if asset_id is None else [asset_id], context=context
    )
    if asset_id is None:
        result["kernels"] = dict(kernels)
        result["machines"] = machine_counts(machines)
    else:
        result["kernel"] = next(iter(kernels), "not_applicable")
        result["machine"] = machines[0] if machines else None
    return result


def asset_software_states(asset_id, now=None):
    """A machine's software with the state of each installation."""
    context = Context(now)
    installations = Installations(context, [asset_id])
    installations.load_evaluations()
    rows = []
    for entry_id in installations.entries_of.get(asset_id, ()):
        name, version, family, _, _ = installations.entries[entry_id]
        identity = installations.identities.get(entry_id)
        rows.append(
            {
                "entry": entry_id,
                "name": name,
                "version": version,
                "family": family,
                "product": identity[3] if identity else "",
                "state": installations.state(entry_id, asset_id),
            }
        )
    return sorted(rows, key=lambda row: (STATES.index(row["state"]), row["name"] or ""))
