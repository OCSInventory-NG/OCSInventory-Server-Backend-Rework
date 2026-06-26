import logging

from django.apps import AppConfig

LOGGER = logging.getLogger(__name__)


def _on_inventory_received(sender, instance, **kwargs):
    """
    Evaluate compliance rules for an asset whenever its inventory is saved.

    Connected to post_save on InventoryBase from ComplianceConfig.ready()
    so that the compliance module never needs to modify any core file.
    """
    try:
        from .engine import evaluate_asset

        evaluate_asset(instance)
    except Exception:
        LOGGER.exception("Compliance evaluation failed for asset %s", instance.id)


class ComplianceConfig(AppConfig):
    """
    Base definition of the django app

    Args:
        AppConfig ([AppConfig])
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "compliance"

    def ready(self):
        from asset.inventory_base.models import InventoryBase
        from django.db.models.signals import post_save

        post_save.connect(
            _on_inventory_received,
            sender=InventoryBase,
            dispatch_uid="compliance_evaluate_on_inventory",
            weak=False,
        )
