import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from automation.tasks.abstractTask import AbstractTask
from deployment.package.models import Package
from config.models import Config
from django.db import DatabaseError

logger = logging.getLogger("mgmt.management.commands.PurgePackages")


class PurgePackages(AbstractTask):
    """
    Automation task to purge old packages from the database.
    The age threshold is configurable in the server config (in months).
    """
    def config_check(self):
        """
        Retrieve the package purge age (in months) from the config.
        """
        try:
            server_conf = Config.objects.filter(name="server").first()
            if not server_conf:
                logger.error("No server config found")
                return None
            logger.debug("Checking server configuration for package purge settings")
            purge_setting = None
            interval = None
            for item in server_conf.value:
                if item["name"] == "purge_deployment_package":
                    purge_setting = item["value"]
                    logger.debug(f"Purge package setting: {purge_setting}")
                if item["name"] == "purge_deployment_package_max_age":
                    interval = item["value"]
                    logger.debug(f"Package purge interval set to {interval} months")
            if purge_setting is None:
                logger.error("purge_deployment_package setting not found in config")
                return None
            if not purge_setting:
                logger.info("Package purge is disabled in configuration")
                return None
            if not interval:
                logger.error("purge_deployment_package_max_age not found in config")
                return None
            return int(interval)
        except DatabaseError as e:
            logger.error(f"Database error while checking config: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in config_check: {e}", exc_info=True)
            return None

    def execute(self):
        """
        Purge packages older than the configured age (in months) from the database.
        """
        try:
            logger.info("Starting PurgePackages task")
            interval = self.config_check()
            if interval is None:
                logger.warning(
                    "Task skipped - no valid interval found. Make sure package purge "
                    "interval is set in server configuration."
                )
                return
            logger.debug(f"Found package purge interval: {interval} months")
            date_limit = datetime.now() - relativedelta(months=interval)
            packages = Package.objects.filter(date_created__lte=date_limit)
            count_packages = packages.count()
            if count_packages == 0:
                logger.warning("No old packages found to purge.")
            else:
                logger.info(f"Found {count_packages} old packages to purge.")
            for pkg in packages:
                logger.debug(
                    "Purging package: id=%s, name=%s, created_at=%s",
                    pkg.id, pkg.name, pkg.date_created
                )
                try:
                    pkg.delete()
                    logger.info(f"Successfully purged package id={pkg.id}")
                except Exception as del_exc:
                    logger.error(
                        f"Failed to purge package id={pkg.id}: {del_exc}",
                        exc_info=True
                    )
            logger.info("PurgePackages task completed successfully.")
        except Exception as e:
            logger.error(f"Error in PurgePackages task: {e}", exc_info=True)
            raise
