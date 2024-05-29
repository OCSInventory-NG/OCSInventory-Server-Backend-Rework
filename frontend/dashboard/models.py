from django.db import models
from ocsinventory_backend.ocs_framework.models import RestrictVisibility

# Create your models here.


class Dashboard(RestrictVisibility):
    """
    This is the dashboard model.
    """

    name = models.CharField(max_length=100)
    layout = models.JSONField()
