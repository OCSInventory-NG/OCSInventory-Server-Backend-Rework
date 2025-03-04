from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.core.management.commands.migrate import Command as MigrateCommand
from django.contrib.auth.models import Group, Permission


class Command(MigrateCommand):
    def handle(self, *args, **options):
        print("\nRunning standard migrations.")
        super().handle(*args, **options)

        print("\nCreating default permissions.")
        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, verbosity=2)
            app_config.models_module = None

        print("\nAssigning permissions to groups.")
        self.assign_group_permissions()

        print("\nFinished all migrations and permission setup.\n")

    def get_group_configs(self):
        return {
            'super-admin': {
                'patterns': ['add_', 'change_', 'delete_', 'view_']
            },
            'admin': {
                'patterns': ['add_', 'change_', 'view_']
            },
            'user': {
                'patterns': ['view_']
            }
        }

    def get_filtered_permissions(self, patterns):
        """Get permissions filtered by patterns"""
        filtered_permissions = set()
        all_permissions = Permission.objects.all()

        for permission in all_permissions:
            # check patterns
            for pattern in patterns:
                if permission.codename.startswith(pattern):
                    filtered_permissions.add(permission)
                    break

        return filtered_permissions

    def assign_group_permissions(self):
        """Assign group permissions"""
        group_configs = self.get_group_configs()

        for group_name, config in group_configs.items():
            try:
                group = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                print(f"""Group '{group_name}' does not exist.
                       Please run migrations first.""")
                continue

            default_permissions = self.get_filtered_permissions(
                config['patterns']
                )
            current_permissions = set(group.permissions.all())

            # diff
            permissions_to_add = default_permissions - current_permissions
            permissions_to_remove = current_permissions - default_permissions

            # applying changes
            if permissions_to_add:
                group.permissions.add(*permissions_to_add)
                print(f"""Added {len(permissions_to_add)}
                       permissions to '{group_name}'""")

            if permissions_to_remove:
                group.permissions.remove(*permissions_to_remove)
                print(f"""Removed {len(permissions_to_remove)}
                       permissions from '{group_name}'""")

            if not permissions_to_add and not permissions_to_remove:
                print(f"No changes needed for group '{group_name}'")
