from django.db import models
from automation.tasks.models import Tasks

# Create your models here.
class History(models.Model):
    task = models.ForeignKey(Tasks, on_delete=models.CASCADE, null=True)
    date = models.DateTimeField()
    comment = models.CharField(max_length=255)
