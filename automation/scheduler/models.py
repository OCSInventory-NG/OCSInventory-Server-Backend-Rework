from django.db import models
from automation.tasks.models import Tasks

# Create your models here.
class Scheduler(models.Model):
    """[summary]

    Args:
        models ([type]): [description]
    """

    RECURENCE_CHOICES = (
        ("hourly", "hourly"), 
        ("daily", "daily"), 
        ("weekly", "weekly"), 
        ("monthly", "monthly")
    )

    name      = models.CharField(max_length=255)
    status    = models.CharField(max_length=255, null=True)
    task      = models.OneToOneField(
        Tasks, on_delete=models.CASCADE, primary_key=True
    )
    recurence = models.CharField(
        max_length=7, choices=RECURENCE_CHOICES, default="daily"
    )
