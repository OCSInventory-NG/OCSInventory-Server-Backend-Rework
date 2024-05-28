from django.contrib.auth.models import User
from django.db import models

# Create your models here.


class Dashboard(models.Model):
    """
    This is the dashboard model.
    """

    user = models.ForeignKey(to=User, on_delete=models.CASCADE, blank=False, null=False)
    name = models.CharField(max_length=100, blank=False, null=False)
    layout = models.JSONField(blank=False, null=False)
