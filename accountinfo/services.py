from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from django.contrib.contenttypes.models import ContentType

ASSET_SLUG = "inventory_base.inventorybase"


def empty_value(datatype):
    """The value a config of this datatype holds when nothing is set"""
    if datatype == "CHECKBOX":
        return []
    if datatype == "SELECT":
        return None
    return ""


def is_empty_value(value):
    return value in (None, "", [], {})


class AccountinfoSearch:
    """
    Find the objects whose administrative data matches a search term

    The search covers what the listing displays, which is not what the JSON
    holds : a text field holds its value, a select holds {"text", "value"} and
    a checkbox holds the ids of its AccountinfoValue rows.

    The rows are walked rather than filtered in SQL. Keys are config ids, so
    they are numeric, and every backend reads a numeric JSON key as an array
    index and returns nothing. Forcing the object form would mean one variant
    per backend, for a table holding a single row per object.
    """

    TEXT_TYPES = ("TEXT", "TEXTAREA")

    def __init__(self, object_slug, datatarget):
        self.object_slug = object_slug
        self.datatarget = datatarget

    def matching_object_ids(self, term):
        """Return the ids of the objects whose displayed data contains term"""
        if not term:
            return set()

        types = dict(
            AccountinfoConfig.objects.filter(datatarget=self.datatarget).values_list(
                "id", "datatype"
            )
        )
        if not types:
            return set()

        needle = term.casefold()
        labels = self._matching_value_ids(term, types)
        matched = set()

        rows = AccountinfoData.objects.filter(object_slug=self.object_slug).values_list(
            "object_id", "accountdata"
        )

        for object_id, data in rows.iterator(chunk_size=2000):
            if not isinstance(data, dict):
                continue
            for key, value in data.items():
                datatype = types.get(self._as_id(key))
                if datatype and self._matches(datatype, value, needle, labels):
                    matched.add(object_id)
                    break

        return matched

    def _matching_value_ids(self, term, types):
        """Checkbox labels live in their own table, resolve them once"""
        checkboxes = [id for id, datatype in types.items() if datatype == "CHECKBOX"]
        if not checkboxes:
            return set()

        return set(
            AccountinfoValue.objects.filter(
                accountinfo_config__in=checkboxes, value__icontains=term
            ).values_list("id", flat=True)
        )

    def _matches(self, datatype, value, needle, labels):
        if datatype in self.TEXT_TYPES:
            return isinstance(value, str) and needle in value.casefold()

        if datatype == "SELECT":
            text = value.get("text") if isinstance(value, dict) else None
            return isinstance(text, str) and needle in text.casefold()

        if datatype == "CHECKBOX":
            picked = value if isinstance(value, list) else []
            return any(self._as_id(entry) in labels for entry in picked)

        return False

    @staticmethod
    def _as_id(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class AgentAdminData:
    """
    Apply the admin_data sent by an agent ({name: value}) to an asset.

    Names match ASSET configs, case ignored. Only empty values are filled;
    a value that cannot be applied is logged and skipped.
    """

    TEXT_TYPES = ("TEXT", "TEXTAREA")
    CHECKBOX_SEPARATOR = ","

    def __init__(self, logger):
        self.logger = logger

    def apply(self, asset, admin_data):
        """Return the names of the configs filled on this asset"""
        device = asset.name
        if admin_data is None or admin_data == {}:
            return []
        if not isinstance(admin_data, dict):
            self.ignore(device, "admin_data is not an object")
            return []

        configs = list(
            AccountinfoConfig.objects.filter(datatarget="ASSET").prefetch_related(
                "accountinfo_values"
            )
        )

        received = {}
        for name, raw in admin_data.items():
            config = self.match(configs, name, device)
            if config is None:
                continue
            value = self.convert(config, raw, device)
            if value is not None:
                received[config] = value

        if not received:
            return []

        data = self.data_of(asset, configs)
        applied = []
        for config, value in received.items():
            key = str(config.id)
            if is_empty_value(data.accountdata.get(key)):
                data.accountdata[key] = value
                applied.append(config.name)
            else:
                self.logger.debug(
                    'Admin data kept for device %s: "%s" is already set',
                    device,
                    config.name,
                    extra={"classname": __name__},
                )

        if applied:
            data.save(update_fields=["accountdata"])
            self.logger.info(
                "Admin data applied for device %s: %s",
                device,
                ", ".join(applied),
                extra={"classname": __name__},
            )
        return applied

    def match(self, configs, name, device):
        """The config named name, an exact match winning over a case match"""
        wanted = name.strip() if isinstance(name, str) else ""
        folded = [
            config
            for config in configs
            if config.name.strip().casefold() == wanted.casefold()
        ]
        if not wanted or not folded:
            self.ignore(device, f'unknown field "{name}"')
            return None
        if len(folded) == 1:
            return folded[0]

        exact = [config for config in folded if config.name.strip() == wanted]
        if len(exact) == 1:
            return exact[0]
        self.ignore(device, f'ambiguous field "{name}"')
        return None

    def convert(self, config, raw, device):
        """The value in the shape the config stores, None when rejected"""
        if not isinstance(raw, str):
            self.ignore(device, f'value of "{config.name}" is not a string')
            return None

        if config.datatype in self.TEXT_TYPES:
            value = raw.strip()
            if not value:
                self.ignore(device, f'empty value for "{config.name}"')
                return None
            return value

        labels = self.labels(config)

        if config.datatype == "SELECT":
            label = raw.strip()
            if not label:
                self.ignore(device, f'empty value for "{config.name}"')
                return None
            picked = labels.get(label.casefold())
            if picked is None:
                self.ignore(device, f'"{label}" is not a value of "{config.name}"')
                return None
            return {"text": picked.value, "value": picked.id}

        if config.datatype == "CHECKBOX":
            tokens = [
                token.strip()
                for token in raw.split(self.CHECKBOX_SEPARATOR)
                if token.strip()
            ]
            if not tokens:
                self.ignore(device, f'empty value for "{config.name}"')
                return None
            ids = []
            for token in tokens:
                picked = labels.get(token.casefold())
                if picked is None:
                    self.ignore(device, f'"{token}" is not a value of "{config.name}"')
                elif picked.id not in ids:
                    ids.append(picked.id)
            return ids or None

        self.ignore(device, f'unsupported type {config.datatype} for "{config.name}"')
        return None

    @staticmethod
    def labels(config):
        """Labels of a SELECT or CHECKBOX, case folded, the lowest id first"""
        labels = {}
        for value in sorted(config.accountinfo_values.all(), key=lambda v: v.id):
            labels.setdefault(value.value.strip().casefold(), value)
        return labels

    @staticmethod
    def data_of(asset, configs):
        """The AccountinfoData of the asset, created blank when missing"""
        data, _ = AccountinfoData.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(asset),
            object_id=asset.id,
            defaults={
                "object_slug": ASSET_SLUG,
                "accountdata": {
                    str(config.id): empty_value(config.datatype) for config in configs
                },
            },
        )
        if not isinstance(data.accountdata, dict):
            data.accountdata = {}
        return data

    def ignore(self, device, reason):
        self.logger.warning(
            "Admin data ignored for device %s: %s",
            device,
            reason,
            extra={"classname": __name__},
        )
