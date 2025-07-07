import logging
from datetime import datetime, timedelta

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
        parser.add_argument(
            "--loglevel",
            type=str,
            choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
            help="Override logging level from server",
        )

    def handle(self, *args, **options):
        """Execute all Tasks"""

        # initialize dynamic logger
        log_manager = DynamicLogLevelManager()

        # logger initialization
        logger = logging.getLogger("mgmt.management.commands")

        # only set log level if explicitly provided in args
        if options["loglevel"]:
            log_manager.set_level_for_logger(
                "mgmt.management.commands", options["loglevel"]
            )
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
        logger.info(f"Found {tasks.count()} active tasks to process")

        # rounded to the minute
        now = datetime.now(tz=self.utc).replace(second=0, microsecond=0)
        exact_now = datetime.now(tz=self.utc)
        logger.debug(f"Current time rounded to minute: {now}")

        for task in tasks:
            logger.info(f"Processing task: {task.name}")
            # minimum intervals between runs
            min_intervals = {
                "hourly": timedelta(hours=1),
                "daily": timedelta(days=1),
                "weekly": timedelta(weeks=1),
                "monthly": timedelta(days=30),
            }

            should_run = False

            # log task.hour safely
            if task.hour is not None:
                logger.debug(
                    f"Task {task.name}: now={now}, task.hour={task.hour}, "
                    f"task.hour.hour={task.hour.hour}, task.hour.minute={task.hour.minute}, "
                    f"exact_now={exact_now}, last_execution={task.last_execution}"
                )
            else:
                logger.debug(
                    f"Task {task.name}: now={now}, task.hour=None, "
                    f"exact_now={exact_now}, last_execution={task.last_execution}"
                )

            scheduled_time_match = False
            if task.recurrence == "hourly":
                scheduled_time_match = True
                logger.debug(f"Task {task.name} is hourly, will run")
            elif (
                task.hour
                and task.hour.hour == now.hour
                and task.hour.minute == now.minute
                and (
                    task.recurrence == "daily"
                    or (
                        task.recurrence == "weekly"
                        and task.day_of_week == now.weekday()
                    )
                    or (task.recurrence == "monthly" and task.day_of_month == now.day)
                )
            ):
                scheduled_time_match = True
                logger.debug(f"Task {task.name} scheduled")
            else:
                logger.debug(f"Task {task.name} not scheduled")

            # check minimum interval since last execution
            interval_passed = False
            if task.last_execution:
                last_exec = task.last_execution.replace(tzinfo=self.utc)
                interval = now - last_exec
                logger.debug(
                    f"Task {task.name} interval since last execution: {interval}, required: {min_intervals[task.recurrence]}"
                )
                if interval >= min_intervals[task.recurrence]:
                    interval_passed = True
                    logger.debug(
                        f"Task {task.name} interval has passed, will run"
                    )
            else:
                # never executed before
                interval_passed = True

            # scheduled time matches OR interval has passed
            if task.recurrence == "hourly":
                should_run = interval_passed
            else:
                should_run = scheduled_time_match or interval_passed

            if should_run:
                try:
                    logger.info(f"Starting task {task.name}")
                    # start history
                    updateHistory(task, f"Starting task {task.name} at {exact_now}", 0)

                    # import and execute task
                    task_class = module_loading.import_string(self.library + task.name)
                    task_instance = task_class()
                    task_instance.execute()

                    task.last_execution = now
                    task.save()

                    logger.info(f"Task {task.name} completed successfully")
                    # completion history
                    updateHistory(
                        task,
                        f"Task {task.name} finished successfully" f" at {exact_now}",
                        1,
                    )

                except Exception as e:
                    error_msg = f"Task {task.name} failed at {exact_now}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    updateHistory(task, error_msg, 2)

        logger.info("Automation tasks completed")
