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

    help = "Test command"
    library = "automation.tasks."
    utc = pytz.UTC

    def handle(self, *args, **options):
        """Execute all Tasks"""

        def updateHistory(task, comment, status):
            """Update history with task and comment"""
            h = History(scheduler=task, comment=comment, status=status)
            h.save()

        tasks = Scheduler.objects.all()
        for task in tasks:
            # Set up task name
            name = task.name
            completeName = self.library + name
            # Configure delta time by recurence
            if task.recurence == "hourly":
                delta = timedelta(hours=1)
            elif task.recurence == "daily":
                delta = timedelta(days=1)
            elif task.recurence == "weekly":
                delta = timedelta(weeks=1)
            else:
                delta = timedelta(days=30)

            now = datetime.now().replace(tzinfo=self.utc)

            # Check if task need to be start
            if (
                task.last_execution is None
                or task.last_execution.replace(tzinfo=self.utc) + delta < now
            ):
                # Save history
                updateHistory(task, "Starting task " + name, 0)

                # Import module task
                taskClass = module_loading.import_string(completeName)
                # Execute task command
                taskClass.execute(taskClass)
                # Update execution date
                task.last_execution = datetime.now(tz=self.utc)
                # Save new date
                task.save()

                # Save finish history
                updateHistory(task, "Task " + name + " finished", 1)
