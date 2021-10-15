from django.db import models

# Create your models here.


class Netgroup(models.Model):
    """
    Netgroup model class definition

    The model will contain the following info
    - Name
    - Description
    """

    name = models.CharField(max_length=128)
    description = models.TextField(max_length=1024)
