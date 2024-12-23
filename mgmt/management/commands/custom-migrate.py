from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.core.management.commands.migrate import Command as MigrateCommand
import json
from pathlib import Path


class Command(MigrateCommand):
    def handle(self, *args, **options):
        super().handle(*args, **options)

        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, verbosity=0)
            app_config.models_module = None

        Group = apps.get_model("auth", "Group")
        Permission = apps.get_model("auth", "Permission")

        for json_file in Path("permission/group_permissions").glob("*.json"):
            try:
                with json_file.open("r") as file:
                    config = json.load(file)
                    permissions = Permission.objects.filter(codename__in=config["permissions"])
                    permissions = [i for i in permissions]
                    Group.objects.get(name=config["name"]).permissions.add(*permissions)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {json_file.name}: {e}")
