import logging
import re
from functools import total_ordering

from automation.rule.context import FIELD_OBJECT, BaseContextResolver

LOGGER = logging.getLogger(__name__)

VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+)*")


@total_ordering
class SoftwareVersion:
    """Compared by leading numeric components: 2.8.100.0 > 2.8.53.0, 2.8 == 2.8.0"""

    def __init__(self, raw, components):
        self.raw = raw
        # trailing zeros dropped so that 2.8 and 2.8.0 compare equal
        while components and components[-1] == 0:
            components = components[:-1]
        self.components = components

    @classmethod
    def parse(cls, value):
        """Return a SoftwareVersion, or None when value has no leading number"""
        if value is None:
            return None
        match = VERSION_PATTERN.match(str(value).strip())
        if not match:
            return None
        return cls(str(value), tuple(int(part) for part in match.group(0).split(".")))

    @classmethod
    def _coerce(cls, other):
        if isinstance(other, cls):
            return other
        return cls.parse(other)

    def __eq__(self, other):
        other = self._coerce(other)
        if other is None:
            return NotImplemented
        return self.components == other.components

    def __lt__(self, other):
        other = self._coerce(other)
        if other is None:
            return NotImplemented
        return self.components < other.components

    def __str__(self):
        return self.raw


class CaseInsensitiveDict(dict):
    """Lowercase keys, case-insensitive lookup: the editor keeps the name as typed"""

    def __getitem__(self, key):
        return super().__getitem__(str(key).lower())


class ComplianceContextResolver(BaseContextResolver):
    """
    Build the JSON Logic context used to evaluate compliance rules against an
    InventoryBase asset.

    Reuses the shared rule-context framework: the scalar asset fields come from
    BaseContextResolver.build() (same source as the inventory_received rules),
    and this resolver only adds the compliance-specific data on top.

    Extra context keys (beyond the base scalar fields):
        - softwares.names    : flat lowercase list for blacklist/presence checks
        - softwares.versions : {software_name: lowest SoftwareVersion}
        - inventory          : custom inventory field values keyed by template
                               field id (surfaced in the UI via inventory fields)
        - group_ids          : list of asset group ids
        - accountinfo         : administrative account data

    get_schema() (inherited) exposes only the software group — the fields that
    are NOT discoverable from the asset model itself — so the rule editor can
    offer them without hard-coding.
    """

    slug = "compliance"
    schema = {
        "softwares": {
            "names": FIELD_OBJECT,
            "versions": FIELD_OBJECT,
        }
    }

    def build(self, asset):
        context = super().build(asset)

        try:
            softwares = list(
                asset.software_dictionary_entries.values("name", "version")
            )
        except Exception:
            LOGGER.exception("Failed to fetch softwares for asset %s", asset.id)
            softwares = []

        versions = CaseInsensitiveDict()
        for software in softwares:
            version = SoftwareVersion.parse(software["version"])
            if not software["name"] or version is None:
                continue
            name = software["name"].lower()
            # same software installed several times: the lowest version is checked
            if name not in versions or version < versions[name]:
                versions[name] = version

        context["softwares"] = {
            "names": [s["name"].lower() for s in softwares if s["name"]],
            "versions": versions,
        }

        try:
            inventory = {}
            for inv_section in asset.inventory_sections.prefetch_related(
                "fields__template_field"
            ):
                for inv_field in inv_section.fields.all():
                    if inv_field.template_field_id is not None:
                        inventory[str(inv_field.template_field_id)] = inv_field.value
            context["inventory"] = inventory
        except Exception:
            LOGGER.exception("Failed to fetch inventory fields for asset %s", asset.id)
            context["inventory"] = {}

        try:
            context["group_ids"] = list(
                asset.assetgroup_set.values_list("id", flat=True)
            )
        except Exception:
            LOGGER.exception("Failed to fetch group_ids for asset %s", asset.id)
            context["group_ids"] = []

        try:
            accountinfo_obj = asset.accountinfo.first()
            context["accountinfo"] = (
                accountinfo_obj.accountdata
                if accountinfo_obj and accountinfo_obj.accountdata
                else {}
            )
        except Exception:
            LOGGER.exception("Failed to fetch accountinfo for asset %s", asset.id)
            context["accountinfo"] = {}

        return context


# Module-level singleton reused by the engine and the context-fields endpoint.
resolver = ComplianceContextResolver()
