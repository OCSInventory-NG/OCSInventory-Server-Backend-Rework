import logging

from automation.tasks.abstractTask import AbstractTask
from security.evaluation import refresh_vulnerabilities
from security.sync import SyncService, locked

logger = logging.getLogger("automation.tasks.SecuritySync")


class SecuritySync(AbstractTask):
    """
    Load the vulnerability data and refresh the scores (KEV, EPSS, CVSS). The
    machines are checked against the new data by VulnerabilityFullScan, and
    those inventoried again by VulnerabilityScan.
    """

    def execute(self):
        logger.info("Starting SecuritySync task")
        with locked():
            results = SyncService.run(progress=logger.info)
            logger.info("Vulnerability data: %s", results)
            refresh_vulnerabilities()
        logger.info("SecuritySync task completed")
