from datetime import datetime, timedelta
import logging
import pytz
from automation.history.models import History
from automation.scheduler.models import Scheduler
from django.core.management.base import BaseCommand
from django.utils import module_loading
from ocsinventory_backend.ocs_framework.logmanager import DynamicLogLevelManager


class Command(BaseCommand):
    """Name of the file equals command, e.g. 'demo'

    Args:
        BaseCommand ([type]): base class for management commands
    """

    help = "Execute scheduled automation tasks"
    library = "automation.tasks."
    utc = pytz.UTC

    def add_arguments(self, parser):
        parser.add_argument('--loglevel', type=str,
                            choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
                            help='Override logging level from server')

    def handle(self, *args, **options):
        """Execute all Tasks"""

        # initialize dynamic logger
        log_manager = DynamicLogLevelManager()
        
        # logger initialization
        logger = logging.getLogger('mgmt.management.commands')

        # only set log level if explicitly provided in args
        if options['loglevel']:
            log_manager.set_level_for_logger("mgmt.management.commands",
                                             options['loglevel'])
            logger.debug(f"Log level overridden to: {options['loglevel']}")
        else:
            logger.debug("Using log level from server")

        logger.info("Starting automation tasks")
        logger.debug(f"Command arguments: {options}")

        def updateHistory(task, comment, status):
            """Update history with task and comment"""
            h = History(scheduler=task, comment=comment, status=status)
            h.save()
            logger.debug(f"History updated for task {task.name}: {comment}")

        tasks = Scheduler.objects.filter(active=True)
        # round current time to the nearest hour to avoid minute/second mismatches
        now = datetime.now().replace(minute=0, second=0, microsecond=0, tzinfo=self.utc)
        logger.debug(f"Current time rounded to hour: {now}")

        for task in tasks:
            #  minimum intervals between runs
            min_intervals = {
                "hourly": timedelta(hours=1),
                "daily": timedelta(days=1),
                "weekly": timedelta(weeks=1),
                "monthly": timedelta(days=30),
            }

            should_run = False

            # for non-hourly tasks, check if we're within the scheduled hour
            if task.recurrence == "hourly":
                should_run = True
                logger.debug(f"Task {task.name} is hourly, will run")
            elif task.hour == now.hour and (
                task.recurrence == "daily"
                or (task.recurrence == "weekly" and task.day_of_week == now.weekday())
                or (task.recurrence == "monthly" and task.day_of_month == now.day)
            ):
                should_run = True
                logger.debug(f"Task {task.name} scheduled for current hour")

            # check minimum interval since last execution
            if should_run and task.last_execution:
                last_exec = task.last_execution.replace(tzinfo=self.utc)
                if now - last_exec < min_intervals[task.recurrence]:
                    should_run = False
                    logger.debug(f"Skipping task"
                                 f" {task.name} - minimum interval not met")

            if should_run:
                try:
                    logger.info(f"Starting task {task.name}")
                    # start history
                    updateHistory(task, f"Starting task {task.name}", 0)

                    # import and execute task
                    task_class = module_loading.import_string(self.library + task.name)
                    task_class.execute(task_class)

                    task.last_execution = now
                    task.save()

                    logger.info(f"Task {task.name} completed successfully")
                    # completion history
                    updateHistory(task, f"Task {task.name} finished successfully", 1)

                except Exception as e:
                    error_msg = f"Task {task.name} failed: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    updateHistory(task, error_msg, 2)

        logger.info("Automation tasks completed")
