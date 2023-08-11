from django.db import models
from automation.scheduler.models import Scheduler

# Create your models here.
class History(models.Model):
    task = models.ForeignKey(Scheduler, on_delete=models.CASCADE, null=True)
    date = models.DateTimeField(auto_now=True)
    comment = models.CharField(max_length=255)
