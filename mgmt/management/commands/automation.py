from django.core.management.base import BaseCommand
from automation.scheduler.models import Scheduler
from django.utils import module_loading

class Command(BaseCommand):
    help = 'Test command'
    library = "automation.tasks."

    def handle(self, *args, **options):
        tasks = Scheduler.objects.all()
        for task in tasks:
            name = task.name
            upperName = task.name.capitalize()

            completeName = self.library + name + "." + upperName

            taskClass = module_loading.import_string(completeName)
            taskClass.execute()
            