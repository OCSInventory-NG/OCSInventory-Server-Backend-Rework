import logging

from automation.tasks.abstractTask import AbstractTask
from inventory.software_identity.services import IdentityService

logger = logging.getLogger("automation.tasks.SoftwareIdentity")


class SoftwareIdentity(AbstractTask):
    """Identify new or outdated software dictionary entries."""

    def execute(self):
        logger.info("Starting SoftwareIdentity task")
        counts = IdentityService.refresh()
        logger.info("SoftwareIdentity task completed: %s", counts)
