import logging

from asset.asset_group.models import AssetGroup
from automation.tasks.abstractTask import AbstractTask
from django.db import DatabaseError
from search.views import SearchView

logger = logging.getLogger("mgmt.management.commands.DynaGroups")


class DynaGroups(AbstractTask):
    """
    DynaGroups class
    Automation tasks handling the re generation assets list for dynamic groups
    Runs the search query and updates the assets list
    """

    def execute(self):
        """
        - get all dynamic groups
        - for each group, get the search query
        - run the search query
        - update the assets list
        """
        try:
            logger.info("Starting DynaGroups task")
            dyna = self.get_dynamic_groups()
            total_groups = dyna.count()
            logger.info(f"Found {total_groups} dynamic groups to process")

            processed = 0
            failed = 0

            for index, group in enumerate(dyna, 1):
                try:
                    logger.debug(
                        f"Processing group {index}/{total_groups}:" f" {group.name}"
                    )
                    search = group.search
                    assets = self.run_search_query(search)
                    self.update_assets_list(group, assets)
                    processed += 1
                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Failed to process group {group.name}: {e}", exc_info=True
                    )

            logger.info(
                f"DynaGroups task completed: {processed} succeeded,"
                f" {failed} failed out of {total_groups} total groups"
            )
        except Exception as e:
            logger.error(f"Critical error in DynaGroups task: {e}", exc_info=True)
            raise

    def get_dynamic_groups(self):
        """
        Get all dynamic groups
        """
        try:
            logger.debug("Fetching all dynamic groups")
            dyna = AssetGroup.objects.filter(is_dynamic=True)
            if not dyna.exists():
                logger.warning("No dynamic groups found in the database")
            return dyna
        except DatabaseError as e:
            logger.error(
                f"Database error while fetching dynamic groups: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error while fetching dynamic groups: {e}", exc_info=True
            )
            raise

    def run_search_query(self, search):
        """
        Run the search query
        """
        try:
            logger.debug(f"Running search query: {search}")
            search_view = SearchView()
            assets = search_view.process_search(search)
            asset_count = assets.count()
            logger.debug(f"Search query returned {asset_count} assets")
            assets = assets.values_list("id", flat=True)
            return assets
        except DatabaseError as e:
            logger.error(
                f"Database error while running search query: {e}", exc_info=True
            )
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error while running search query: {e}", exc_info=True
            )
            return []

    def update_assets_list(self, group, assets):
        """
        Update the assets list
        """
        try:
            asset_count = len(assets)
            logger.debug(
                f"Updating assets list for group {group.name}"
                f" with {asset_count} assets"
            )
            group.assets.set(assets)
            group.save()
            logger.info(f"Successfully updated assets list for group {group.name}")
        except DatabaseError as e:
            logger.error(
                f"Database error updating assets list for group {group.name}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating assets list for group {group.name}: {e}",
                exc_info=True,
            )
            raise
