from django.apps import AppConfig


class GroupConfig(AppConfig):
    """
    Base definition of the django app

    Args:
        AppConfig ([AppConfig])
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "group"

    def ready(self):
        import group.signals
