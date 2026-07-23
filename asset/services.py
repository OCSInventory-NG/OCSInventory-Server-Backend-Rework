import logging
from typing import Dict, Optional

from config.models import Config


class ReconciliationService:
    """Handle asset reconciliation logic."""

    LOGGER = logging.getLogger(__name__)

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

        try:
            config = Config.objects.get(name="server")
            for item in config.value:
                if item.get("name") == "duplicate_reconciliation":
                    selection = item.get("value", "uuid")
                    if selection == "uuid, name":
                        fields = ["uuid", "name"]
                    elif selection == "uuid, srcmac":
                        fields = ["uuid", "srcmac"]
                    else:
                        # default or "uuid"
                        fields = ["uuid"]
                    cls.LOGGER.debug(
                        f"Reconciliation fields configured as: {fields}",
                        extra={"classname": __name__},
                    )
                    return fields
            fields = ["uuid"]
            cls.LOGGER.debug(
                f"Using default reconciliation fields: {fields}",
                extra={"classname": __name__},
            )
            return fields
        except Config.DoesNotExist:
            cls.LOGGER.warning(
                """No server configuration found, will be using uuid only as
                  default reconciliation field""",
                extra={"classname": __name__},
            )
            fields = ["uuid"]
            cls.LOGGER.debug(
                f"Using default reconciliation fields: {fields}",
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

        try:
            config = Config.objects.get(name="server")
            for item in config.value:
                if item.get("name") == "legacy_duplicate_reconciliation":
                    fields = item.get("value") or ["uuid"]
                    cls.LOGGER.debug(
                        f"Legacy reconciliation fields configured as: {fields}",
                        extra={"classname": __name__},
                    )
                    return fields
            fields = ["uuid"]
            cls.LOGGER.debug(
                f"Using default legacy reconciliation fields: {fields}",
                extra={"classname": __name__},
            )
            return fields
        except Config.DoesNotExist:
            cls.LOGGER.warning(
                """No server configuration found, will be using uuid only as
                  default reconciliation field""",
                extra={"classname": __name__},
            )
            fields = ["uuid"]
            cls.LOGGER.debug(
                f"Using default legacy reconciliation fields: {fields}",
                extra={"classname": __name__},
            )
            return fields

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

    def format_reconciliation_info(cls, data: Dict[str, Optional[str]]):
        fields = cls.get_reconciliation_fields()
        values = [f"{field}={data.get(field, 'unknown')}" for field in fields]
        return f"({' - '.join(values)})"
