import logging

from automation.tasks.abstractTask import AbstractTask
from inventory.software_identity.cpe.sync import sync_cpe_index

logger = logging.getLogger("automation.tasks.CpeIndexSync")


class CpeIndexSync(AbstractTask):
    """Refresh the CPE index when the NVD CPE dictionary changed."""

    def execute(self):
        logger.info("Starting CpeIndexSync task")
        rebuilt = sync_cpe_index()
        logger.info(
            "CpeIndexSync task completed: %s",
            "index rebuilt" if rebuilt else "feed unchanged",
        )
