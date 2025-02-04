from django.db import models


class Scheduler(models.Model):

    RECURRENCE_CHOICES = (
        ("hourly", "hourly"),
        ("daily", "daily"),
        ("weekly", "weekly"),
        ("monthly", "monthly"),
    )

    name = models.CharField(max_length=100)
    description = models.CharField(max_length=1024)
    active = models.BooleanField()
    recurrence = models.CharField(
        max_length=7, choices=RECURRENCE_CHOICES, default="daily"
    )
    last_execution = models.DateTimeField(null=True)
    hour = models.IntegerField(null=True, blank=True)
    day_of_week = models.IntegerField(null=True, blank=True)
    day_of_month = models.IntegerField(null=True, blank=True)
