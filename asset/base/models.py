from django.db import models


# Create your models here.
class Base(models.Model):
    """
    Asset's base model class definition

    The model will contain the following info
    - Name
    - Description
    - Serial
    - OS Name
    - OS Version
    - UUID
    - SRCIP
    - SRCMAC
    - Domain
    """

    name = models.CharField(max_length=50, null=False)
    description = models.CharField(max_length=255)
    serial = models.CharField(max_length=255, null=False)
    osname = models.CharField(max_length=255, null=False)
    osversion = models.CharField(max_length=255, null=False)
    uuid = models.CharField(max_length=255, null=False, unique=True)
    srcip = models.CharField(max_length=255)
    srcmac = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    last_update = models.DateTimeField(auto_now=True)
