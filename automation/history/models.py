from django.db import models
from automation.scheduler.models import Scheduler

# Create your models here.
class History(models.Model):
    scheduler = models.ForeignKey(Scheduler, on_delete=models.CASCADE, null=False)
    date = models.DateTimeField(auto_now=True)
    status = models.IntegerField(null=False)
    comment = models.CharField(max_length=255)
