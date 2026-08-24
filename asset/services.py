import logging
from typing import Dict, Optional

from config.models import Config


class ReconciliationService:
    """Handle asset reconciliation logic."""

    LOGGER = logging.getLogger(__name__)

    # never used to match an asset
    BLACKLIST = ("", "Empty", None)

    class UnusableReconciliationValue(ValueError):
        """Raised when a reconciliation field holds no usable value."""

        def __init__(self, field, value):
            self.field = field
            self.value = value
            super().__init__(
                f"Field '{field}' holds no value usable for "
                f"reconciliation ({value!r})."
            )

    @classmethod
    def _get_server_entry(cls, name):
        """
        Read an entry of the "server" configuration.

        Returns the whole entry, so callers can use its declared `options` as
        well as its value. None when the configuration or the entry is missing.
        """
        try:
            config = Config.objects.get(name="server")
        except Config.DoesNotExist:
            cls.LOGGER.warning(
                """No server configuration found, will be using uuid only as
                  default reconciliation field""",
                extra={"classname": __name__},
            )
            return None

        for item in config.value:
            if item.get("name") == name:
                return item
        return None

    @classmethod
    def get_reconciliation_fields(cls):
        """
        Get the fields used for reconciliation from the server configuration

        Possible values are:
         - "uuid"
         - "uuid, name"
         - "uuid, srcmac"
         Default is "uuid"
        """
        entry = cls._get_server_entry("duplicate_reconciliation")
        selection = entry.get("value") if entry else None
        if selection == "uuid, name":
            fields = ["uuid", "name"]
        elif selection == "uuid, srcmac":
            fields = ["uuid", "srcmac"]
        else:
            # default or "uuid"
            fields = ["uuid"]

        cls.LOGGER.debug(
            f"Reconciliation fields "
            f"({'config' if selection is not None else 'default'}): {fields}",
            extra={"classname": __name__},
        )
        return fields

    @classmethod
    def get_legacy_reconciliation_fields(cls):
        """
        Get the fields used for reconciliation on the legacy endpoint from the
        server configuration.

        Value is a list of one or more fields among:
         - "uuid", "name", "serial", "srcmac"
         Default is ["uuid"]
        """
        entry = cls._get_server_entry("legacy_duplicate_reconciliation") or {}
        configured = entry.get("value") or []
        if isinstance(configured, str):
            configured = [configured]
        allowed = entry.get("options") or ["uuid", "name", "serial", "srcmac"]

        fields = [field for field in configured if field in allowed]
        unknown = [field for field in configured if field not in allowed]
        if unknown:
            cls.LOGGER.warning(
                f"Ignoring unknown legacy reconciliation field(s): {unknown}",
                extra={"classname": __name__},
            )
        if not fields:
            if configured:
                cls.LOGGER.warning(
                    f"No usable legacy reconciliation field in {configured!r}, "
                    "falling back to ['uuid']",
                    extra={"classname": __name__},
                )
            cls.LOGGER.debug(
                "Legacy reconciliation fields (default): ['uuid']",
                extra={"classname": __name__},
            )
            return ["uuid"]

        cls.LOGGER.debug(
            f"Legacy reconciliation fields (config): {fields}",
            extra={"classname": __name__},
        )
        return fields

    @classmethod
    def get_reconciliation_filter(cls, data: Dict[str, Optional[str]], fields=None):
        """
        Build a filter for asset lookup from the reconciliation fields (config)
        """
        if fields is None:
            fields = cls.get_reconciliation_fields()
        filter_dict = {}
        for field in fields:
            if field not in data:
                raise ValueError(f"""Missing field '{field}'
                                  required for reconciliation.""")
            filter_dict[field] = data[field]
        return filter_dict

    @classmethod
    def get_legacy_reconciliation_filter(cls, data, fields=None):
        """
        Build the asset lookup filter for the legacy endpoint.

        args:
            data: the parsed inventory
            fields: reconciliation fields, read from the config when omitted

        returns:
            the filter to look the asset up with

        raises:
            UnusableReconciliationValue: when not even the deviceid is usable
        """
        if fields is None:
            fields = cls.get_legacy_reconciliation_fields()

        filter_dict = {}
        for field in fields:
            value = data.get(field)
            if value in cls.BLACKLIST:
                cls.LOGGER.warning(
                    f"Cannot reconcile device "
                    f"{data.get('name', 'unknown')} on '{field}': no usable "
                    f"value ({value!r}), falling back to uuid",
                    extra={"classname": __name__},
                )
                return cls._uuid_reconciliation_filter(data)
            filter_dict[field] = value
        return filter_dict

    @classmethod
    def _uuid_reconciliation_filter(cls, data):
        """
        Fallback filter, used when the configured fields cannot identify the
        device. Reproduces the behaviour that predates the configurable
        reconciliation: one asset per deviceid.
        """
        uuid = data.get("uuid")
        if uuid in cls.BLACKLIST:
            raise cls.UnusableReconciliationValue("uuid", uuid)
        return {"uuid": uuid}

    @classmethod
    def format_reconciliation_info(cls, data: Dict[str, Optional[str]], fields=None):
        """
        Human readable summary of the values a device is reconciled on.

        `fields` must be passed by the legacy endpoint: its fields come from
        another configuration entry, and may differ from the configured ones
        when an unusable value forced a fallback.
        """
        if fields is None:
            fields = cls.get_reconciliation_fields()
        values = [f"{field}={data.get(field, 'unknown')}" for field in fields]
        return f"({' - '.join(values)})"
