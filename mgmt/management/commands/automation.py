from django.core.management.base import BaseCommand
from automation.scheduler.models import Scheduler
from django.utils import module_loading
from datetime import datetime, timedelta
import pytz

class Command(BaseCommand):
    help = 'Test command'
    library = "automation.tasks."
    utc=pytz.UTC

    def handle(self, *args, **options):
        tasks = Scheduler.objects.all()
        for task in tasks:
            name = task.name
            upperName = task.name.capitalize()
            completeName = self.library + name + "." + upperName

            if(task.recurence == 'hourly'):
                delta = timedelta(hours=1)
            elif(task.recurence == 'daily'):
                delta = timedelta(days=1)
            elif(task.recurence == 'weekly'):
                delta = timedelta(weeks=1)
            else:
                delta = timedelta(days=30)

            now = datetime.now().replace(tzinfo=self.utc)

            if(task.last_exec is None or task.last_exec.replace(tzinfo=self.utc) + delta < now):
                taskClass = module_loading.import_string(completeName)
                taskClass.execute()

                task.last_exec = datetime.now(tz=self.utc)
                task.save()
                print("Done")
            