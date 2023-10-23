from django.db import models


class AuthMethod(models.Model):
    """
    AuthMethod model class definition

    Fields :
    - Name
    - Priority
    - Enabled
    """

    name = models.CharField(max_length=255, unique=True)
    priority = models.IntegerField(unique=True)
    enabled = models.BooleanField(default=False)
