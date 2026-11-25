"""
What the API shows: the open exposures grouped per vulnerability, ordered by
the priority criteria, exclusions applied; a machine's exposures and the
state of its software; the coverage of the fleet.
"""

from collections import Counter, defaultdict

from asset.inventory_base.models import InventoryBase
from django.db.models import Count, F, Max, Q
from security import config as security_config
from security.config import PRIORITY_CRITERIA
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
MACHINE_ORDERING = ("name", "platform", "status", "reason", "support_end")


def priority(ordering=None):
    """The active order: the given criteria, else the settings', first first."""
    if ordering:
        return list(ordering)
    configured = [
        c for c in security_config.current().priority if c in PRIORITY_CRITERIA
    ]
    return configured or list(PRIORITY_CRITERIA)


# The priority criteria in SQL: larger first, unknown last
RANKING = {
    "kev": F("vulnerability__kev").desc(),
    "score": F("vulnerability__cvss_score").desc(nulls_last=True),
    "epss": F("vulnerability__epss").desc(nulls_last=True),
    "machines": F("machines").desc(),
}


def _exposures(family=None, asset_id=None, now=None):
    """The open exposures, of a machine or a family when given, exclusions applied."""
    exposures = Exposure.objects.filter(closed_at__isnull=True)
    if asset_id is not None:
        exposures = exposures.filter(asset_id=asset_id)
    if family:
        exposures = exposures.filter(platform_family=family)
    return active_exclusions(now).exclude_from(exposures)


def _matching(
    level_filter=None,
    fix=None,
    family=None,
    asset_id=None,
    search="",
    kev=None,
    now=None,
):
    """
    The exposures of the vulnerabilities the filters keep: a vulnerability
    is kept or left out whole, with all its products and machines.
    """
    exposures = _exposures(family, asset_id, now)
    matching = exposures
    if level_filter:
        matching = matching.filter(vulnerability__level=level_filter)
    if kev is not None:
        matching = matching.filter(vulnerability__kev=kev)
    if fix is not None:
        fixed = exposures.exclude(fixed_version="").values("vulnerability_id")
        matching = (
            matching.filter(vulnerability_id__in=fixed)
            if fix
            else matching.exclude(vulnerability_id__in=fixed)
        )
    search = (search or "").strip()
    if search:
        named = exposures.filter(
            Q(product__icontains=search) | Q(software_name__icontains=search)
        ).values("vulnerability_id")
        matching = matching.filter(
            Q(vulnerability__vuln_id__icontains=search) | Q(vulnerability_id__in=named)
        )
    return matching


def ranked_vulnerabilities(ordering=None, **filters):
    """
    (queryset, active order): one row per vulnerability the list shows, its
    id and its machine count, in the active priority order, paged in SQL.
    """
    order = priority(ordering)
    ranked = (
        _matching(**filters)
        .values("vulnerability_id")
        .annotate(machines=Count("asset_id", distinct=True))
        .order_by(*(RANKING[c] for c in order), "vulnerability__vuln_id")
    )
    return ranked, order


def vulnerability_page(ranked, family=None, asset_id=None, now=None):
    """
    The rows of the list for ranked rows, a page or all of them: products and
    fixes read for these vulnerabilities only.
    """
    ranked = list(ranked)
    ids = [row["vulnerability_id"] for row in ranked]
    details = defaultdict(
        lambda: {
            "products": {},
            "fixed": set(),
            "channels": set(),
            "methods": set(),
            "first_seen": None,
        }
    )
    exposures = _exposures(family, asset_id, now).filter(vulnerability_id__in=ids)
    for exposure in exposures.values(
        "vulnerability_id",
        "product",
        "software_name",
        "version",
        "fixed_version",
        "fix_channel",
        "method",
        "first_seen",
    ):
        detail = details[exposure["vulnerability_id"]]
        detail["products"][(exposure["product"], exposure["version"])] = exposure[
            "software_name"
        ]
        if exposure["fixed_version"]:
            detail["fixed"].add(exposure["fixed_version"])
            detail["channels"].add(exposure["fix_channel"])
        detail["methods"].add(exposure["method"])
        if (
            detail["first_seen"] is None
            or exposure["first_seen"] < detail["first_seen"]
        ):
            detail["first_seen"] = exposure["first_seen"]

    vulnerabilities = Vulnerability.objects.in_bulk(ids)
    rows = []
    for row in ranked:
        vulnerability = vulnerabilities[row["vulnerability_id"]]
        detail = details[vulnerability.id]
        products = sorted(
            (
                {"product": product, "version": version, "name": name}
                for (product, version), name in detail["products"].items()
            ),
            key=lambda p: (p["product"], p["version"]),
        )
        rows.append(
            {
                "vuln_id": vulnerability.vuln_id,
                "summary": vulnerability.summary,
                "kev": vulnerability.kev,
                "kev_date_added": vulnerability.kev_date_added,
                "cvss_score": vulnerability.cvss_score,
                "cvss_version": vulnerability.cvss_version,
                "epss": vulnerability.epss,
                "epss_percentile": vulnerability.epss_percentile,
                "level": vulnerability.level,
                "distro_rating": vulnerability.distro_rating,
                "source": "osv" if detail["methods"] == {METHOD_OSV} else "nvd",
                "machines": row["machines"],
                "products": products[:PRODUCTS_SHOWN],
                "product_count": len(products),
                "fix_available": bool(detail["fixed"]),
                "fixed_versions": sorted(detail["fixed"])[:PRODUCTS_SHOWN],
                "fix_channels": sorted(c or "standard" for c in detail["channels"]),
                "first_seen": detail["first_seen"],
            }
        )
    return rows


def vulnerability_rows(ordering=None, **filters):
    """
    (rows, active order): the vulnerabilities shown by the list, all of them,
    in the active priority order. Filters as _matching.
    """
    ranked, order = ranked_vulnerabilities(ordering, **filters)
    rows = vulnerability_page(
        ranked, filters.get("family"), filters.get("asset_id"), filters.get("now")
    )
    return rows, order


def vulnerability_summary(**filters):
    """
    Totals of the vulnerabilities the list shows with the same filters: per
    level, exploited, with a fix, and the distinct machines impacted; the
    machines the scan does not cover, counted apart (machine and family
    filters only: the others select vulnerabilities, not machines).
    """
    matching = _matching(**filters)
    levels = Counter()
    exploited = with_fix = 0
    for row in matching.values(
        "vulnerability_id", "vulnerability__level", "vulnerability__kev"
    ).annotate(fixes=Count("id", filter=~Q(fixed_version=""))):
        levels[row["vulnerability__level"]] += 1
        exploited += row["vulnerability__kev"]
        with_fix += row["fixes"] > 0
    asset_id = filters.get("asset_id")
    machines = machine_rows(
        None if asset_id is None else [asset_id], filters.get("family")
    )
    return {
        "total": sum(levels.values()),
        "levels": {name: levels[name] for name in LEVELS},
        "kev": exploited,
        "fix_available": with_fix,
        "machines": matching.values("asset_id").distinct().count(),
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
        "level": vulnerability.level,
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


# The columns of a machine's exposures and what they sort on
EXPOSURE_ORDERING = {
    "vuln_id": "vulnerability__vuln_id",
    "summary": "vulnerability__summary",
    "score": "vulnerability__cvss_score",
    "kev": "vulnerability__kev",
    "epss": "vulnerability__epss",
    "software": "software_name",
    "version": "version",
    "fix": "fixed_version",
    "method": "method",
    "first_seen": "first_seen",
    "closed_on": "closed_at",
    "resolution": "resolution",
}


def asset_exposures(
    asset_id, status="open", excluded=None, search="", ordering=None, now=None
):
    """
    A machine's exposures, open or closed, those an exclusion leaves out or
    in when excluded is given: in the priority order, or on a column of
    EXPOSURE_ORDERING ("-" before it for descending). A queryset, paged in SQL.
    """
    exposures = Exposure.objects.filter(asset_id=asset_id).select_related(
        "vulnerability"
    )
    if status == "open":
        exposures = exposures.filter(closed_at__isnull=True)
    elif status == "closed":
        exposures = exposures.filter(closed_at__isnull=False)
    if excluded is not None:
        left_out = active_exclusions(now).left_out()
        if excluded:
            exposures = exposures.filter(left_out) if left_out else exposures.none()
        elif left_out:
            exposures = exposures.exclude(left_out)
    search = (search or "").strip()
    if search:
        exposures = exposures.filter(
            Q(vulnerability__vuln_id__icontains=search)
            | Q(vulnerability__summary__icontains=search)
            | Q(software_name__icontains=search)
            | Q(product__icontains=search)
            | Q(version__icontains=search)
            | Q(fixed_version__icontains=search)
            | Q(advisory_id__icontains=search)
        )
    if ordering:
        field = F(EXPOSURE_ORDERING[ordering.removeprefix("-")])
        sort = [
            (
                field.desc(nulls_last=True)
                if ordering.startswith("-")
                else field.asc(nulls_last=True)
            )
        ]
    else:
        sort = [RANKING[c] for c in priority() if c != "machines"]
    # a total order: a page never repeats nor skips a row
    return exposures.order_by(*sort, "vulnerability__vuln_id", "product", "id")


def asset_exposure_rows(exposures, asset_id, now=None):
    """The rows of a machine's exposures, a page or all of them."""
    exclusions = active_exclusions(now)
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
                "level": vulnerability.level,
                "kev": vulnerability.kev,
                "epss": vulnerability.epss,
                "machines": 1,
            }
        )
        rows.append(row)
    return rows


def asset_exposure_counts(asset_id, now=None):
    """
    A machine's open exposures, those an exclusion leaves out, and the
    vulnerabilities with a fix among the others.
    """
    exposures = Exposure.objects.filter(asset_id=asset_id, closed_at__isnull=True)
    shown = active_exclusions(now).exclude_from(exposures)
    with_fix = shown.exclude(fixed_version="").values("vulnerability_id").distinct()
    count = shown.count()
    return {
        "open": count,
        "fix": with_fix.count(),
        "excluded": exposures.count() - count,
    }


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


def sort_machine_rows(rows, ordering):
    """
    By a column of MACHINE_ORDERING, "-" before it for descending; the empty
    values last. Status and reason follow the order of the tests.
    """
    key = {
        "name": lambda row: row["name"].casefold() if row["name"] else None,
        "platform": lambda row: (
            (row["family"], row["platform"]) if row["family"] else None
        ),
        "status": lambda row: row["status"] == MACHINE_COVERED,
        "reason": lambda row: (
            NOT_COVERED_REASONS.index(row["reason"]) if row["reason"] else None
        ),
        "support_end": lambda row: row["support_end"],
    }[ordering.removeprefix("-")]
    filled = sorted(
        (row for row in rows if key(row) is not None),
        key=key,
        reverse=ordering.startswith("-"),
    )
    return filled + [row for row in rows if key(row) is None]


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
    machines = machine_rows(None if asset_id is None else [asset_id], context=context)
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
