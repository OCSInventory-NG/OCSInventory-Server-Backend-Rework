from django.db import models

# Create your models here.
class Log(models.Model):
    assetID = models.TextField(max_length=255, null=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(max_length=255)