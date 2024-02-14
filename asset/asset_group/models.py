from asset.inventory_base.models import InventoryBase
from django.db import models
from django.db.models.fields.json import JSONField


class AssetGroup(models.Model):
    """
    Asset Group model class definition

    The model will contain the following info:
    - Name
    - Description
    - Is Dynamic : True/False
    - Search : stores the search used to regenerate the assets if dynamic
    - Assets : either cached assets for a dynamic group or static assets for a
        static group
    """

    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    is_dynamic = models.BooleanField(default=False)
    search = JSONField(blank=True, null=True)
    assets = models.ManyToManyField(InventoryBase, blank=True)
