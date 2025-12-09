import logging

from automation.tasks.abstractTask import AbstractTask
from inventory.software.services import SoftwareDictionaryService


logger = logging.getLogger("automation.tasks.SoftwareDictionary")


class SoftwareDictionary(AbstractTask):
    """
    Automation task that rebuilds the software dictionary for all assets.
    """

    def execute(self):
        logger.info("Starting SoftwareDictionary automation task")
        SoftwareDictionaryService.rebuild()
        logger.info("SoftwareDictionary automation task completed")
