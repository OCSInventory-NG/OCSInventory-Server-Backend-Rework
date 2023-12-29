from django.db import models

from auth.auth_config.models import AuthConfig

class AuthMapping(models.Model):
    """
    AuthMapping model class definition

    Fields :
    - Auth config
    - external field
    - internal field
    """

    auth_config = models.ForeignKey(
        AuthConfig,
        related_name="mappings",
        on_delete=models.CASCADE,
        null=True
    )
    external_field = models.CharField(max_length=255)
    internal_field = models.CharField(max_length=255)
