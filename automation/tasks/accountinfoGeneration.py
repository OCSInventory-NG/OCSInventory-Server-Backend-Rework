import logging

from accountinfo.views import AccountinfoDataViewSet
from asset.inventory_base.models import InventoryBase
from automation.tasks.abstractTask import AbstractTask
from config.models import Config
from django.db import DatabaseError

logger = logging.getLogger("mgmt.management.commands.AccountInfoGeneration")


class AccountInfoGeneration(AbstractTask):
    """
    Task to create missing AccountinfoData entries for assets. This task
    is intended to be run using the automation/scheduler module.
    """

    def execute(self):
        """
        Find all assets without AccountinfoData and create entries for them
        """
        try:
            logger.info("Starting AccountInfoGeneration task")
            if self.config_check():
                logger.debug("Accountinfo generation is enabled in automation mode")
                assets = self.get_assets()
                logger.debug(f"Found {assets.count()} assets to process")
                self.generate_accountinfo(assets)
            else:
                logger.warning(
                    "Task skipped - accountinfo generation"
                    " not enabled in automation mode"
                )
        except Exception as e:
            logger.error(
                f"Critical error in AccountInfoGeneration task: {e}", exc_info=True
            )
            raise

    def config_check(self):
        """
        Check if accountinfo generation is set to automation mode
        """
        try:
            server_conf = Config.objects.filter(name="server").first()
            if not server_conf:
                logger.error("No server config found")
                return False

            logger.debug(
                "Checking server configuration for" " accountinfo generation settings"
            )
            for item in server_conf.value:
                if item["name"] == "accountinfo_generation":
                    mode = item["value"]
                    logger.debug(f"Accountinfo generation mode: {mode}")
                    return mode == "automation"

            logger.error("accountinfo_generation not found in config")
            return False
        except DatabaseError as e:
            logger.error(f"Database error while checking config: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in config_check: {e}", exc_info=True)
            return False

    def get_assets(self):
        """
        Get all assets that need accountinfo generation
        """
        try:
            logger.debug("Fetching all assets for accountinfo generation")
            assets = InventoryBase.objects.all()
            if not assets.exists():
                logger.warning("No assets found in the database")
            return assets
        except DatabaseError as e:
            logger.error(f"Database error while fetching assets: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching assets: {e}", exc_info=True)
            raise

    def generate_accountinfo(self, assets):
        """
        Generate accountinfo for the given assets
        """
        try:
            total_assets = assets.count()
            logger.info(f"Starting accountinfo generation for {total_assets} assets")
            processed = 0
            failed = 0

            for asset in assets:
                try:
                    AccountinfoDataViewSet.generate_accountinfo(
                        asset, "inventory_base.inventorybase"
                    )
                    processed += 1
                    if processed % 100 == 0:
                        logger.debug(f"Processed {processed}/{total_assets} assets")
                except DatabaseError as e:
                    failed += 1
                    logger.error(
                        f"Database error generating accountinfo"
                        f" for asset {asset.id}: {e}",
                        exc_info=True,
                    )
                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Error generating accountinfo for asset {asset.id}: {e}",
                        exc_info=True,
                    )

            logger.info(
                f"Accountinfo generation completed: {processed} succeeded,"
                f" {failed} failed out of {total_assets} total assets"
            )
        except Exception as e:
            logger.error(
                f"Critical error in accountinfo generation process: {e}", exc_info=True
            )
            raise
