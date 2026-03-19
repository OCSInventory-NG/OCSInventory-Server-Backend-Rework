import logging

from automation.tasks.abstractTask import AbstractTask
from inventory.software.services import SoftwareDictionaryService
from asset.inventory_base.models import InventoryBase

logger = logging.getLogger("automation.tasks.SoftwareDictionary")


class SoftwareDictionary(AbstractTask):
    """
    Automation task that rebuilds the software dictionary for all assets.
    """

    def execute(self):
        if not SoftwareDictionaryService.should_refresh_on_automation():
            logger.info(
                "Software dictionary set to refresh during inventory "
                "collection; skipping automation run"
            )
            return

        logger.info("Starting SoftwareDictionary automation task")

        non_legacy_assets = InventoryBase.objects.exclude(template__os="LEG")
        SoftwareDictionaryService.rebuild(asset_ids=[a.id for a in non_legacy_assets])
        logger.info("SoftwareDictionary automation task completed")
