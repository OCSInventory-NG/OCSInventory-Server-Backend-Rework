import logging
from datetime import date, timedelta
from django.db import DatabaseError

from asset.log.models import Log
from automation.tasks.abstractTask import AbstractTask
from config.models import Config

logger = logging.getLogger("mgmt.management.commands.PurgeAgentLog")


class PurgeAgentLog(AbstractTask):
    """
    Task to purge agent logs. This task
    is intended to be run using the automation/scheduler module.
    """

    def execute(self):
        """
        Find all agent logs before interval and purge them
        """
        try:
            logger.info("Starting PurgeAgentLog task")
            interval = self.config_check()
            if interval:
                logger.debug(f"Found purge interval: {interval} days")
                logs = self.get_logs(interval)
                logger.debug(f"Found {logs.count()} logs to purge")
                self.clean_logs(logs)
            else:
                logger.warning(
                    "Task skipped - no valid interval found. Make sure"
                    " agent logs purge interval is set in server configuration.")
        except Exception as e:
            logger.error(f"Critical error in PurgeAgentLog task: {e}", exc_info=True)
            raise

    def config_check(self):
        """
        Check if agent log purge is enabled and retrieve interval
        """
        try:
            server_conf = Config.objects.filter(name="server").first()
            if not server_conf:
                logger.error("No server config found")
                return False

            logger.debug("Checking server configuration for purge settings")
            purge_setting = None
            interval = None

            for item in server_conf.value:
                if item["name"] == "purge_agent_log":
                    purge_setting = item["value"]
                    logger.debug(f"Purge agent log setting: {purge_setting}")
                if item["name"] == "purge_agent_log_interval":
                    interval = item["value"]
                    logger.debug(f"Purge interval set to {interval} days")

            if purge_setting is None:
                logger.error("purge_agent_log setting not found in config")
                return False

            if not purge_setting:
                logger.info("Agent log purge is disabled in configuration")
                return False

            if not interval:
                logger.error("purge_agent_log_interval not found in config")
                return False

            return interval

        except DatabaseError as e:
            logger.error(f"Database error while checking config: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in config_check: {e}", exc_info=True)
            return False

    def get_logs(self, interval):
        """
        Get all logs older than today - interval
        """
        try:
            date_limit = date.today() - timedelta(days=interval)
            logger.debug(f"Fetching logs older than {date_limit}")
            items = Log.objects.filter(timestamp__lte=date_limit)
            if not items.exists():
                logger.warning(f"No logs found older than {date_limit}")
            return items
        except DatabaseError as e:
            logger.error(f"Database error while fetching logs: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching logs: {e}", exc_info=True)
            raise

    def clean_logs(self, logs):
        """
        Purge logs
        """
        try:
            count = logs.count()
            logger.info(f"Purging {count} agent logs")

            try:
                logs.delete()
                logger.info(f"Successfully purged {count} agent logs")
            except DatabaseError as e:
                logger.error(f"Database error while purging logs: {e}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"Unexpected error while purging logs: {e}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Error in clean_logs process: {e}", exc_info=True)
            raise
