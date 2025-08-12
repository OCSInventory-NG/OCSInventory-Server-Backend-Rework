import logging

from asset.inventory_base.models import InventoryBase
from automation.tasks.abstractTask import AbstractTask
from django.db import DatabaseError
from django.db.models import Count

logger = logging.getLogger("mgmt.management.commands.MergeLegacy")


class MergeLegacy(AbstractTask):
    """
    Task to clean up legacy inventories. This task identifies duplicate names
    and removes the legacy assets if they have corresponding 3.x assets.
    """

    def execute(self):
        """
        Find all legacy assets (OCS-NG) and clean them up
        """
        try:
            logger.info("Starting MergeLegacy task")
            self.cleanup_legacy_assets()
        except Exception as e:
            logger.error(f"Critical error in MergeLegacy task: {e}", exc_info=True)
            raise

    def cleanup_legacy_assets(self):
        """
        Find all name duplicates and clean up legacy assets that have corresponding 3.x
        """
        try:
            # get names with multiple assets
            duplicate_names = (
                InventoryBase.objects.values("name")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )

            total_duplicate_names = duplicate_names.count()
            logger.info(f"Found {total_duplicate_names} name(s) with multiple assets")

            processed = 0
            failed = 0
            cleaned = 0

            for name_data in duplicate_names:
                try:
                    name = name_data["name"]
                    assets = InventoryBase.objects.filter(name=name)

                    # split
                    legacy_assets = [a for a in assets if "OCS-NG" in a.agent]
                    rework_assets = [a for a in assets if "OCS-NG" not in a.agent]

                    # clean up if we have both legacy and new assets for the same name
                    if legacy_assets and rework_assets:
                        logger.debug(
                            f"Found {len(legacy_assets)} legacy and "
                            f"{len(rework_assets)} 3.x assets for name '{name}', "
                            f"cleaning up legacy assets"
                        )

                        for legacy in legacy_assets:
                            legacy.delete()
                            cleaned += 1
                    else:
                        logger.debug(
                            f"Name '{name}' has {len(legacy_assets)} legacy and "
                            f"{len(rework_assets)} 3.x assets, no cleanup needed"
                        )

                    processed += 1

                except DatabaseError as e:
                    failed += 1
                    logger.error(
                        f"Database error processing name '{name}': {e}",
                        exc_info=True,
                    )
                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Error processing name '{name}': {e}",
                        exc_info=True,
                    )

            logger.info(
                f"Legacy cleanup completed: {processed} names processed, "
                f"{cleaned} legacy assets cleaned,"
                f" {failed} failed"
            )
        except Exception as e:
            logger.error(
                f"Critical error in legacy cleanup process: {e}", exc_info=True
            )
            raise
