import logging

from automation.tasks.abstractTask import AbstractTask
from django.db import DatabaseError

logger = logging.getLogger("mgmt.management.commands.ComplianceEvaluation")


class ComplianceEvaluation(AbstractTask):
    """
    ComplianceEvaluation class
    Automation task handling the re-evaluation of all compliance rules
    against all assets. Persists results in ComplianceResult.
    """

    def execute(self):
        """
        - get all assets
        - for each asset, evaluate all enabled compliance rules
        - persist results
        """
        try:
            logger.info("Starting ComplianceEvaluation task")
            from asset.inventory_base.models import InventoryBase

            assets = InventoryBase.objects.all()
            total_assets = assets.count()
            logger.info(f"Found {total_assets} assets to evaluate")

            processed = 0
            failed = 0

            for index, asset in enumerate(assets, 1):
                try:
                    logger.debug(
                        f"Evaluating asset {index}/{total_assets}: {asset.name}"
                    )
                    self.evaluate_asset(asset)
                    processed += 1
                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Failed to evaluate asset {asset.name}: {e}", exc_info=True
                    )

            logger.info(
                f"ComplianceEvaluation task completed: {processed} succeeded,"
                f" {failed} failed out of {total_assets} total assets"
            )
        except Exception as e:
            logger.error(
                f"Critical error in ComplianceEvaluation task: {e}", exc_info=True
            )
            raise

    def evaluate_asset(self, asset):
        """
        Evaluate all enabled compliance rules against a single asset
        """
        try:
            logger.debug(f"Running compliance evaluation for asset {asset.name}")
            from compliance.engine import evaluate_asset
            evaluate_asset(asset)
        except DatabaseError as e:
            logger.error(
                f"Database error while evaluating asset {asset.name}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error while evaluating asset {asset.name}: {e}",
                exc_info=True,
            )
            raise
