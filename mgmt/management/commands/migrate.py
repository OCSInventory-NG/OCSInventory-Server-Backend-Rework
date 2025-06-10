from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.contrib.auth.models import Group, Permission
from django.core.management.commands.migrate import Command as MigrateCommand
import logging
from ocsinventory_backend.ocs_framework.logmanager import DynamicLogLevelManager



class Command(MigrateCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--loglevel', type=str,
                            choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
                            help='Override logging level from server')

    def handle(self, *args, **options):
        # initialize dynamic log manager first
        log_manager = DynamicLogLevelManager()

        # logger initialization
        logger = logging.getLogger('mgmt.management.commands')
        logger.debug(f"Command arguments: {options}")

        # only set log level if explicitly provided in args
        if options['loglevel']:
            log_manager.set_level_for_logger("mgmt.management.commands",
                                             options['loglevel'])
            logger.debug(f"Log level overridden to: {options['loglevel']}")
        else:
            logger.debug("Using log level from server")

        logger.info("Running standard migrations")
        super().handle(*args, **options)

        logger.info("Creating default permissions")
        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, verbosity=2)
            app_config.models_module = None

        logger.info("Assigning permissions to groups")
        self.assign_group_permissions()

        logger.info("Finished all migrations and permission setup")

    def get_group_configs(self):
        return {
            "super-admin": {"patterns": ["add_", "change_", "delete_", "view_"]},
            "admin": {"patterns": ["add_", "change_", "view_"]},
            "user": {"patterns": ["view_"]},
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
        logger = logging.getLogger('mgmt.management.commands')
        group_configs = self.get_group_configs()

        for group_name, config in group_configs.items():
            try:
                group = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                logger.error(
                    f"Group '{group_name}' does not exist. "
                    "Please run migrations first."
                )
                continue

            default_permissions = self.get_filtered_permissions(config["patterns"])
            current_permissions = set(group.permissions.all())

            # diff
            permissions_to_add = default_permissions - current_permissions
            permissions_to_remove = current_permissions - default_permissions

            # applying changes
            if permissions_to_add:
                group.permissions.add(*permissions_to_add)
                logger.info(
                    f"Added {len(permissions_to_add)} "
                    f"permissions to '{group_name}'"
                )

            if permissions_to_remove:
                group.permissions.remove(*permissions_to_remove)
                logger.info(
                    f"Removed {len(permissions_to_remove)} "
                    f"permissions from '{group_name}'"
                )

            if not permissions_to_add and not permissions_to_remove:
                logger.debug(f"No changes needed for group '{group_name}'")
