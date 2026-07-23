from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

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
        ("CHECKBOX", "Checkbox"),
    )

    ACC_TARGET_CHOICES = (
        ("ASSET", "Assets"),
        ("IPDISCOVER", "IPDiscover"),
    )

    name = models.CharField(max_length=100)
    description = models.CharField(max_length=512)

    datatype = models.CharField(max_length=10, choices=ACC_TYPE_CHOICES, default="TEXT")

    datatarget = models.CharField(
        max_length=10, choices=ACC_TARGET_CHOICES, default="ASSET"
    )

    class Meta:
        """Define unique constraints"""

        constraints = [
            models.UniqueConstraint(
                fields=["name", "datatarget"], name="unique_accountinfo"
            )
        ]

    def delete(self, *args, **kwargs):
        """Override delete to reflect the change in accountdata"""
        # get all accountinfo data entries
        accountinfo_data_entries = AccountinfoData.objects.all()

        # update accountdata to remove the deleted config
        for entry in accountinfo_data_entries:
            if entry.accountdata and str(self.id) in entry.accountdata:
                entry.accountdata.pop(str(self.id))
                entry.save()

        super().delete(*args, **kwargs)


class AccountinfoValue(models.Model):
    """
    Accountinfo value model class definition

    The model will contain the following info
    - accountconfig link
    - value
    """

    accountinfo_config = models.ForeignKey(
        AccountinfoConfig, related_name="accountinfo_values", on_delete=models.CASCADE
    )
    value = models.CharField(max_length=100)


class AccountinfoData(models.Model):
    """
    Accountinfo data model class definition

    The model will contain the following info
    - accountdata : JSON representation of the account infos
    """

    accountdata = models.JSONField(blank=True, null=True)

    object_slug = models.CharField(null=True, max_length=100)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        """Define unique constraints"""

        constraints = [
            models.UniqueConstraint(
                fields=["object_id", "object_slug"],
                name="unique_accountinfo_data",
            )
        ]
