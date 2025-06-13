from datetime import datetime, timedelta

import pytz
from automation.history.models import History
from automation.scheduler.models import Scheduler
from django.core.management.base import BaseCommand
from django.utils import module_loading


class Command(BaseCommand):
    """Name of the file equals command, e.g. 'demo'

    Args:
        BaseCommand ([type]): base class for management commands
    """

    help = "Execute scheduled automation tasks"
    library = "automation.tasks."
    utc = pytz.UTC

    def handle(self, *args, **options):
        """Execute all Tasks"""

        def updateHistory(task, comment, status):
            """Update history with task and comment"""
            h = History(scheduler=task, comment=comment, status=status)
            h.save()

        tasks = Scheduler.objects.filter(active=True)
        # round current time to the nearest hour to avoid minute/second mismatches
        now = datetime.now().replace(minute=0, second=0, microsecond=0, tzinfo=self.utc)

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
            elif (
                task.hour.hour == now.hour
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
                should_run = True

            # check minimum interval since last execution
            if should_run and task.last_execution:
                last_exec = task.last_execution.replace(tzinfo=self.utc)
                if now - last_exec < min_intervals[task.recurrence]:
                    should_run = False

            if should_run:
                try:
                    # start history
                    updateHistory(task, f"Starting task {task.name}", 0)

                    # import and execute task
                    task_class = module_loading.import_string(self.library + task.name)
                    task_class.execute(task_class)

                    task.last_execution = now
                    task.save()

                    # completion history
                    updateHistory(task, f"Task {task.name} finished successfully", 1)

                except Exception as e:
                    updateHistory(task, f"Task {task.name} failed: {str(e)}", 2)
