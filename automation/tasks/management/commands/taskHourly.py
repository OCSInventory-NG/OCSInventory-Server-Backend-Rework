from django.core.management.base import BaseCommand, CommandError
from automation.tasks.models import Tasks

class Command(BaseCommand):
    help = 'Test command'

    def handle(self, *args, **options):
        tasks = Tasks.objects.get(recurence="hourly")
        for task in tasks:
            print(task.name)
