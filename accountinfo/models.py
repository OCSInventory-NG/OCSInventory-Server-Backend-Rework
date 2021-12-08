from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# Create your models here.


class AccountinfoConfig(models.Model):
    """
    Accountinfo configuration model class definition

    The model will contain the following info
    - Name
    - Description
    - datatype
    - datatarget
    """

    ACC_TYPE_CHOICES = (
        ("TEXT", "Text"),
        ("TEXTAREA", "Textarea"),
        ("SELECT", "Select"),
        ("CHECKBOX", "Checkbox")
    )

    ACC_TARGET_CHOICES = (
        ("ASSET", "Assets"),
        ("SNMP", "SNMP"),
        ("IPDISCOVER", "IPDiscover")
    )

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=512)

    datatype = models.CharField(
        max_length=10,
        choices=ACC_TYPE_CHOICES,
        default="TEXT"
    )

    datatarget = models.CharField(
        max_length=10,
        choices=ACC_TARGET_CHOICES,
        default="ASSET"
    )


class AccountinfoValue(models.Model):
    """
    Accountinfo value model class definition

    The model will contain the following info
    - accountconfig link
    - value
    """
    accountinfo_config = models.ForeignKey(
        AccountinfoConfig, related_name="accountinfo_values", on_delete=models.CASCADE)
    value = models.CharField(max_length=100)


class AccountinfoData(models.Model):
    """
    Accountinfo data model class definition

    The model will contain the following info
    - accountdata : JSON representation of the account infos
    """
    accountdata = models.JSONField()

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
