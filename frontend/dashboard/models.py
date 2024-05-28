from django.db import models

# Create your models here.


class Dashboard(models.Model):
    """
    This is the dashboard model.
    """

    # user = models.ForeignKey()
    name = models.CharField(max_length=100)
    layout = models.JSONField()
