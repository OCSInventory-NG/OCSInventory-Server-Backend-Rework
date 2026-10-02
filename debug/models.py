from django.db import models


class DebugMode(models.Model):
    """
    Only carries the debug.view_debugmode permission, no table is created.
    Kept with the standard view_ naming so the default groups get it.
    """

    class Meta:
        managed = False
        default_permissions = ("view",)
