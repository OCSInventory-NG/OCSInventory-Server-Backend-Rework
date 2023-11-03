from django.db import models


class AuthConfig(models.Model):
    """
    AuthConfig model class definition

    Fields :
    - Auth method
    - JSON config
    - Priority (two enabled configs for the same auth_method 
    cannot have the same priority)
    - Enabled
    """

    auth_method = models.ForeignKey(
        "auth_method.AuthMethod",
        related_name="auth_configs",
        on_delete=models.CASCADE,
    )
    config = models.JSONField()
    priority = models.IntegerField()
    enabled = models.BooleanField(default=False)
