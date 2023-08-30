from django.db import models
from deployment.package.models import Package
from asset.base.models import Base


class Result(models.Model):
    """
    Result model class definition

    The model will contain the following info
    - Package ID
    - Linked asset
    - Name
    - Status
    - Comment
    - Date of creation
    """

    package = models.ForeignKey(
        Package, related_name="package", on_delete=models.CASCADE, null=True
    )
    asset = models.ForeignKey(
        Base, related_name="asset", on_delete=models.CASCADE, null=True
    )
    name = models.CharField(max_length=128)
    status = models.IntegerField()
    comment = models.TextField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
