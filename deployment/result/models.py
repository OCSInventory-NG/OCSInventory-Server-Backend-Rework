from asset.asset_group.models import AssetGroup
from asset.inventory_base.models import InventoryBase
from deployment.package.models import Package
from django.db import models


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
        Package, related_name="result", on_delete=models.CASCADE, null=True
    )
    asset = models.ForeignKey(
        InventoryBase, related_name="results", on_delete=models.CASCADE, null=True
    )
    group = models.ForeignKey(
        AssetGroup, related_name="results", on_delete=models.CASCADE, null=True
    )
    name = models.CharField(max_length=128)
    status = models.IntegerField()
    comment = models.TextField(null=True)
    date_created = models.DateTimeField(auto_now_add=True)
