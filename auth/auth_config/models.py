from django.db import models


class AuthConfig(models.Model):
    """
    AuthConfig model class definition

    Fields :
    - Auth method
    - JSON config
    - Priority (unique : two configs cannot have the same priority)
    - Enabled
    """

    auth_method = models.ForeignKey(
        "auth_method.AuthMethod",
        related_name="auth_configs",
        on_delete=models.CASCADE,
    )
    config = models.JSONField()
    priority = models.IntegerField()
    # TODO : is enabled needed here? allow user to enable/disable a specific config could prove useful
    enabled = models.BooleanField(default=False)
