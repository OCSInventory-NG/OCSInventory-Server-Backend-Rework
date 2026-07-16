import logging

from automation.rule.context import FIELD_OBJECT, BaseContextResolver

LOGGER = logging.getLogger(__name__)


class ComplianceContextResolver(BaseContextResolver):
    """
    Build the JSON Logic context used to evaluate compliance rules against an
    InventoryBase asset.

    Reuses the shared rule-context framework: the scalar asset fields come from
    BaseContextResolver.build() (same source as the inventory_received rules),
    and this resolver only adds the compliance-specific data on top.

    Extra context keys (beyond the base scalar fields):
        - softwares.names    : flat lowercase list for blacklist/presence checks
        - softwares.versions : {software_name: major_version}
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
                asset.software_dictionary_entries.values("name", "major_version")
            )
        except Exception:
            LOGGER.exception("Failed to fetch softwares for asset %s", asset.id)
            softwares = []

        context["softwares"] = {
            "names": [s["name"].lower() for s in softwares if s["name"]],
            "versions": {
                s["name"].lower(): s["major_version"]
                for s in softwares
                if s["name"] and s["major_version"] is not None
            },
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
