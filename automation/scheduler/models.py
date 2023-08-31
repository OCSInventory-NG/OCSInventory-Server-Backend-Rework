from django.db import models

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

    name      = models.CharField(max_length=100)
    description = models.CharField(max_length=1024)
    active    = models.BooleanField()
    recurence = models.CharField(
        max_length=7, choices=RECURENCE_CHOICES, default="daily"
    )
    last_execution = models.DateTimeField(null=True)
