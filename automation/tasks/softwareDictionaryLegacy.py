import logging

from automation.tasks.abstractTask import AbstractTask
from asset.inventory_base.models import InventoryBase
from inventory.software.services import SoftwareDictionaryService

logger = logging.getLogger("automation.tasks.SoftwareDictionaryLegacy")


class SoftwareDictionaryLegacy(AbstractTask):
    """
    Automation task that rebuilds the software dictionary for all legacy assets.
    """

    def execute(self):
        if not SoftwareDictionaryService.should_refresh_on_automation():
            logger.info(
                "Software dictionary set to refresh during inventory "
                "collection; skipping automation run"
            )
            return
            
        logger.info("Starting SoftwareDictionaryLegacy automation task")

        legacy_assets = InventoryBase.objects.filter(template__os="LEG")
        SoftwareDictionaryService.refresh_legacy_asset([a.id for a in legacy_assets])

        logger.info("SoftwareDictionaryLegacy automation task completed")