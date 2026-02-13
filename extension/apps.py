from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _sync_extensions_post_migrate(**kwargs):
    from .sync import sync_extensions_from_filesystem

    sync_extensions_from_filesystem()


class ExtensionConfig(AppConfig):
    """
    Base definition of the django app

    Args:
        AppConfig ([AppConfig])
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "extension"

    def ready(self):
        post_migrate.connect(
            _sync_extensions_post_migrate,
            sender=self,
            dispatch_uid="extension_post_migrate_sync",
            weak=False,
        )
