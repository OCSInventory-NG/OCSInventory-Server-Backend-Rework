from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue


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
