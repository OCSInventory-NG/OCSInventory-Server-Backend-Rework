from django.apps import AppConfig


class NetworkConfig(AppConfig):
    """
    Base definition of the django app

    Args:
        AppConfig ([AppConfig])
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ipdiscover.network'
