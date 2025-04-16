from django.apps import AppConfig


class FieldConfig(AppConfig):
    """
    Base definition of the django app

    Args:
        AppConfig ([AppConfig])
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "inventory.field"

    def ready(self):
        try:
            import inventory.field.models
        except ImportError:
            pass
