"""
Each machine's security, stored for the asset list and the search: excluded
from the scan, not scanned (not covered, or none of its software evaluated
yet), else the worst level of its open vulnerabilities, or not vulnerable;
with its open vulnerabilities (exclusions applied, one counted once whatever
the products), those whose every open exposure has a fix, and per level.
"""

from collections import Counter, defaultdict

from asset.inventory_base.models import InventoryBase
from django.db import transaction
from django.db.models import Count, Q
from inventory.software.models import SoftwareDictionary
from security.evaluation import Context
from security.exclusions import active_exclusions, visible_exposures
from security.models import AssetSecurity, Evaluation

LEVELS = ("critical", "high", "medium", "low", "unknown")
EXCLUDED = "excluded"
NOT_SCANNED = "not_scanned"
NOT_VULNERABLE = "not_vulnerable"
STATUSES = (EXCLUDED, NOT_SCANNED, *LEVELS, NOT_VULNERABLE)
# Sorting order: the most serious status ranks highest
RANKS = {
    EXCLUDED: 0,
    NOT_SCANNED: 1,
    NOT_VULNERABLE: 2,
    "unknown": 3,
    "low": 4,
    "medium": 5,
    "high": 6,
    "critical": 7,
}
BATCH = 1000


def _scanned(asset_ids):
    """Machines with a product of their software evaluated, fresh data or not."""
    return set(
        SoftwareDictionary.assets.through.objects.filter(
            inventorybase_id__in=asset_ids,
            softwaredictionary__identity__product__in=Evaluation.objects.values(
                "product"
            ),
        )
        .values_list("inventorybase_id", flat=True)
        .distinct()
    )


def compute(asset_ids=None, now=None):
    """
    {asset_id: AssetSecurity, unsaved} of the given machines (all when
    None).
    """
    # Imported here: security.reading builds on this module
    from security.reading import MACHINE_COVERED, machine_rows

    context = Context(now)
    machines = machine_rows(asset_ids, context=context)
    ids = [row["asset"] for row in machines]
    covered = {row["asset"] for row in machines if row["status"] == MACHINE_COVERED}
    scanned = covered & _scanned(ids)
    excluded = active_exclusions(context.now).scan_wide_assets()

    levels = defaultdict(Counter)
    fixable = Counter()
    exposures = visible_exposures(context.now)
    if asset_ids is not None:
        exposures = exposures.filter(asset_id__in=ids)
    for asset_id, vulnerability_level, unfixed in (
        exposures.values("asset_id", "vulnerability_id", "vulnerability__level")
        .annotate(unfixed=Count("id", filter=Q(fixed_version="")))
        .values_list("asset_id", "vulnerability__level", "unfixed")
        .iterator(chunk_size=BATCH * 10)
    ):
        levels[asset_id][vulnerability_level] += 1
        if not unfixed:
            fixable[asset_id] += 1

    result = {}
    for asset_id in ids:
        counts = levels.get(asset_id, Counter())
        if asset_id in excluded:
            status = EXCLUDED
        elif asset_id not in scanned:
            status = NOT_SCANNED
        else:
            status = next((name for name in LEVELS if counts[name]), NOT_VULNERABLE)
        result[asset_id] = AssetSecurity(
            asset_id=asset_id,
            status=status,
            rank=RANKS[status],
            cves=sum(counts.values()),
            cves_fixable=fixable[asset_id],
            updated_at=context.now,
            **{name: counts[name] for name in LEVELS},
        )
    return result


def refresh(asset_ids=None, now=None):
    """Stores the security of the given machines (all when None)."""
    rows = compute(asset_ids, now)
    with transaction.atomic():
        AssetSecurity.objects.bulk_create(
            rows.values(),
            batch_size=BATCH,
            update_conflicts=True,
            unique_fields=["asset"],
            update_fields=[
                "status",
                "rank",
                "cves",
                "cves_fixable",
                *LEVELS,
                "updated_at",
            ],
        )
    return len(rows)


def summaries(asset_ids):
    """
    The stored security of the given machines that exist, as the asset list
    reads it; a machine without row is not scanned yet.
    """
    stored = AssetSecurity.objects.in_bulk(asset_ids)
    rows = []
    for asset_id in sorted(
        InventoryBase.objects.filter(id__in=asset_ids).values_list("id", flat=True)
    ):
        row = stored.get(asset_id)
        rows.append(
            {
                "asset": asset_id,
                "status": row.status if row else NOT_SCANNED,
                "cves": row.cves if row else 0,
                "cves_fixable": row.cves_fixable if row else 0,
                "levels": {name: getattr(row, name) if row else 0 for name in LEVELS},
            }
        )
    return rows
