from django.db import models


class AuthMapping(models.Model):
    """
    AuthMapping model class definition

    Fields :
    - Auth method
    - Auth config
    - external field
    - internal field
    """

    auth_method = models.ForeignKey(
        "auth_method.AuthMethod",
        related_name="auth_mappings",
        on_delete=models.CASCADE,
    )
    auth_config = models.ForeignKey(
        "auth_config.AuthConfig",
        related_name="auth_mappings",
        on_delete=models.CASCADE,
    )
    external_field = models.CharField(max_length=255)
    internal_field = models.CharField(max_length=255)
