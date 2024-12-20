from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.core.management.commands.migrate import Command as MigrateCommand
import json


class Command(MigrateCommand):
    def handle(self, *args, **options):
        super().handle(*args, **options)

        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, verbosity=0)
            app_config.models_module = None

        Group = apps.get_model("auth", "Group")
        Permission = apps.get_model("auth", "Permission")
        group_permissions = json.load(open("group_permissions.json"))

        for group in group_permissions:
            permissions = Permission.objects.filter(codename__in=group["permissions"])
            permissions = [i for i in permissions]
            Group.objects.get(name=group["name"]).permissions.add(*permissions)
