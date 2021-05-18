from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'test this please'

    def add_arguments(self, parser):
        parser.add_argument('msg', type=str, help='insert help msg')

    def handle(self, *args, **options):
        msg = options['msg']
        self.stdout.write(str(msg))
