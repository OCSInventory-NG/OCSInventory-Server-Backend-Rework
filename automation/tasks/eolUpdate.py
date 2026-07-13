import logging

from automation.tasks.abstractTask import AbstractTask
from django.db import DatabaseError

logger = logging.getLogger("mgmt.management.commands.EOLUpdate")


class EOLUpdate(AbstractTask):
    """
    EOLUpdate task.
    Resolves the OS EOL status for every asset and persists it in
    AssetEOLStatus. Uses EOLCache — only hits endoflife.date when the
    cache entry is absent or older than 24 h.
    """

    def execute(self):
        try:
            logger.info("Starting EOLUpdate task")
            from asset.inventory_base.models import InventoryBase

            assets = InventoryBase.objects.all()
            total = assets.count()
            logger.info("Found %d assets to update", total)

            processed = 0
            failed = 0

            for index, asset in enumerate(assets, 1):
                try:
                    logger.debug(
                        "Updating EOL for asset %d/%d: %s", index, total, asset.name
                    )
                    self.update_asset_eol_status(asset)
                    processed += 1
                except Exception as e:
                    failed += 1
                    logger.error(
                        "Failed to update EOL for asset %s: %s",
                        asset.name, e, exc_info=True
                    )

            logger.info(
                "EOLUpdate task completed: %d succeeded, %d failed out of %d total assets",
                processed, failed, total,
            )
        except Exception as e:
            logger.error("Critical error in EOLUpdate task: %s", e, exc_info=True)
            raise

    def update_asset_eol_status(self, asset):
        try:
            from compliance.engine import update_asset_eol_status
            update_asset_eol_status(asset)
        except DatabaseError as e:
            logger.error(
                "Database error while updating EOL for asset %s: %s",
                asset.name, e, exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error while updating EOL for asset %s: %s",
                asset.name, e, exc_info=True
            )
            raise
