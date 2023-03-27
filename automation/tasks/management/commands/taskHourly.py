from django.core.management.base import BaseCommand, CommandError
from autoaction.tasks.models import Tasks

class Command(BaseCommand):
    help = 'Test command'

    def handle(self, *args, **options):
        tasks = Tasks.objects.get(recurence="hourly")
        for task in tasks:
            print(task.name)
