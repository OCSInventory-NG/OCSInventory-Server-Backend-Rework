import logging

from asset.log.models import Log
from automation.tasks.abstractTask import AbstractTask
from config.models import Config
from datetime import timedelta, date

logger = logging.getLogger(__name__)


class PurgeAgentLog(AbstractTask):
    """
    Task to purge agent logs. This task
    is intended to be run using the automation/scheduler module.
    """

    def execute(self):
        """
        Find all agent logs before interval and purge them
        """
        logger.info("Starting PurgeAgentLog task")
        interval = self.config_check()
        if interval:
            logs = self.get_logs(interval)
            self.clean_logs(logs)

    def config_check():
        """
        Check if agent log purge is enabled and retrieve interval
        """
        server_conf = Config.objects.filter(name="server").first()
        purge = False
        if not server_conf:
            logger.error("No server config found")
            return False
        for item in server_conf.value:
            if item["name"] == "purge_agent_log":
                purge = item["value"]
            if item["name"] == "purge_agent_log_interval" and purge:
                return item["value"]
        logger.error("purge_agent_log not found or not enabled in config")
        return False
    
    def get_logs(interval):
        """
        Get all logs older than today - interval
        """
        date_limit = date.today() - timedelta(days=interval)
        items = Log.objects.filter(date__lte=date_limit)
        return items
    
    def clean_logs(logs):
        """
        Purge logs
        """
        try:
            logger.info(f"{logs.count()} agent logs should be removed")
            logs.delete()
        except Exception as e:
            logger.error(f"Error agent logs purge: {e}")