from django.db import models
from ocsinventory_backend.ocs_framework.models import RestrictVisibility


class DashboardLayout(RestrictVisibility):
    """
    This is the dashboard layout model

    Fields:
    - name: layout name
    - layout: JSON layout data (x, y, w, h, i, etc.)
    """

    name = models.CharField(max_length=100)
    layout = models.JSONField()
