from django.db import models

# Create your models here.
class Inventory(models.Model):
    """
    Asset's base model class definition

    The model will contain the following info
    - inventJson
    - key
    - value
    - finalValue
    """

    assetId = models.TextField(max_length=255, null=True)
    sectionId = models.ForeignKey('self', on_delete=models.CASCADE, related_name='child', null=True)
    sectionName = models.TextField(max_length=255, null=True)
    sectionJson = models.JSONField(null=True)