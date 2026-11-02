import logging

from automation.tasks.abstractTask import AbstractTask
from security.scan import ScanService
from security.sync import SyncService, locked

logger = logging.getLogger("automation.tasks.SecuritySync")


class SecuritySync(AbstractTask):
    """Load the vulnerability data, then scan every machine."""

    def execute(self):
        logger.info("Starting SecuritySync task")
        with locked():
            results = SyncService.run(progress=logger.info)
            logger.info("Vulnerability data: %s", results)
            counts = ScanService.run(progress=logger.info, lock=False)
        logger.info("SecuritySync task completed: %s", counts)
