import logging

LOGGER = logging.getLogger(__name__)

_ASSET_FIELDS = [
    "id",
    "name",
    "description",
    "serial",
    "osname",
    "osversion",
    "uuid",
    "srcip",
    "srcmac",
    "domain",
    "agent",
]


def build_context(asset):
    """
    Build the JSON Logic evaluation context for a given InventoryBase instance.

    Context keys:
        - scalar InventoryBase fields (name, osname, osversion, …)
        - softwares       : list of {name, publisher, version, …}
        - softwares_names : flat lowercase list for fast blacklist checks
        - inventory       : custom inventory fields keyed by template field id
        - group_ids       : list of asset group ids
        - accountinfo     : administrative account data
    """
    context = {field: getattr(asset, field, None) for field in _ASSET_FIELDS}

    try:
        softwares = list(
            asset.software_dictionary_entries.values(
                "name",
                "publisher",
                "version",
                "major_version",
                "minor_version",
                "patch_version",
            )
        )
    except Exception:
        LOGGER.exception("Failed to fetch softwares for asset %s", asset.id)
        softwares = []

    context["softwares"] = softwares
    context["softwares_names"] = [s["name"].lower() for s in softwares if s["name"]]
    context["softwares_versions"] = {
        s["name"].lower(): s["major_version"]
        for s in softwares
        if s["name"] and s["major_version"] is not None
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
        context["group_ids"] = list(asset.assetgroup_set.values_list("id", flat=True))
    except Exception:
        LOGGER.exception("Failed to fetch group_ids for asset %s", asset.id)
        context["group_ids"] = []

    try:
        accountinfo_obj = asset.accountinfo.first()
        context["accountinfo"] = accountinfo_obj.accountdata if accountinfo_obj and accountinfo_obj.accountdata else {}
    except Exception:
        LOGGER.exception("Failed to fetch accountinfo for asset %s", asset.id)
        context["accountinfo"] = {}

    return context
