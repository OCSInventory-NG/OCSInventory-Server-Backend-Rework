from django.contrib.auth.models import User
from ocsinventory_backend.ocs_framework.models import RestrictVisibility
from django.db import models

# Create your models here.


class Dashboard(RestrictVisibility):
    """
    This is the dashboard model.
    """

    name = models.CharField(max_length=100, blank=False, null=False)
    layout = models.JSONField(blank=False, null=False)
