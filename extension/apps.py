from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ExtensionConfig(AppConfig):
    """
    Base definition of the django app

    Args:
        AppConfig ([AppConfig])
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "extension"

    def ready(self):
        from .sync import sync_extensions_from_filesystem

        post_migrate.connect(
            lambda **kwargs: sync_extensions_from_filesystem(),
            sender=self,
            dispatch_uid="extension_post_migrate_sync",
        )
