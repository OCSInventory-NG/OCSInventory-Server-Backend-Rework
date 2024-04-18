from django.db import models

# Create your models here.


class Config(models.Model):
    """[summary]

    Args:
        models ([type]): [description]
    """

    class Meta:
        ordering = ["name"]

    name = models.CharField(max_length=100, primary_key=True)
    value = models.JSONField()
