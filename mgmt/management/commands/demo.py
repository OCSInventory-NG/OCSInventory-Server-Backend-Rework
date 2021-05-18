from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Name of the file equals command, e.g. 'demo'

    Args:
        BaseCommand ([type]): base class for management commands
    """
    help = 'any arg passed to this cmd will be printed back'

    def add_arguments(self, parser):
        parser.add_argument('msg', type=str, help='string')

    def handle(self, *args, **options):
        msg = options['msg']
        # let's just print back the arg
        self.stdout.write(str(msg))
