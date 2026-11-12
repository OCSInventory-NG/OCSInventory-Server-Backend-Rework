"""
Exclusions, applied when reading: a vulnerability (or the whole scan) left
out for a machine or for the machines of a group, dynamic groups included
(their cached machines). An expired exclusion no longer applies.
"""

from collections import defaultdict

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from security.models import Exclusion, Exposure

WHOLE_SCAN = ""


class ActiveExclusions:
    """The exclusions in force, per machine: {asset_id: {vuln_id or ""}}."""

    def __init__(self, per_asset):
        self.per_asset = per_asset

    def scan_wide_assets(self):
        return {
            asset_id
            for asset_id, vuln_ids in self.per_asset.items()
            if WHOLE_SCAN in vuln_ids
        }

    def excludes(self, asset_id, vuln_id):
        vuln_ids = self.per_asset.get(asset_id)
        return bool(vuln_ids) and (WHOLE_SCAN in vuln_ids or vuln_id in vuln_ids)

    def excluded_vulnerability_assets(self):
        """{vuln_id: {asset_id}} of the per vulnerability exclusions."""
        result = defaultdict(set)
        for asset_id, vuln_ids in self.per_asset.items():
            for vuln_id in vuln_ids:
                if vuln_id != WHOLE_SCAN:
                    result[vuln_id].add(asset_id)
        return result


def in_force(now=None):
    now = now or timezone.now()
    return Exclusion.objects.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def active_exclusions(now=None):
    per_asset = defaultdict(set)
    group_exclusions = defaultdict(set)
    for vuln_id, asset_id, group_id in in_force(now).values_list(
        "vuln_id", "asset_id", "group_id"
    ):
        if asset_id is not None:
            per_asset[asset_id].add(vuln_id)
        elif group_id is not None:
            group_exclusions[group_id].add(vuln_id)
    if group_exclusions:
        from asset.asset_group.models import AssetGroup

        members = AssetGroup.assets.through.objects.filter(
            assetgroup_id__in=group_exclusions
        ).values_list("assetgroup_id", "inventorybase_id")
        for group_id, asset_id in members:
            per_asset[asset_id] |= group_exclusions[group_id]
    return ActiveExclusions(dict(per_asset))


def visible_exposures(now=None):
    """
    The open exposures no exclusion in force leaves out, in SQL: neither the
    whole scan nor their vulnerability excluded for their machine or one of
    its groups. What the search and the machine statuses read.
    """
    excluding = in_force(now).filter(
        Q(vuln_id=WHOLE_SCAN) | Q(vuln_id=OuterRef("vulnerability__vuln_id")),
        Q(asset_id=OuterRef("asset_id")) | Q(group__assets=OuterRef("asset_id")),
    )
    return Exposure.objects.filter(closed_at__isnull=True).exclude(Exists(excluding))
