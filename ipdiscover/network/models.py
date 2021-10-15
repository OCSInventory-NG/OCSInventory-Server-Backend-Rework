from django.db import models
from ipdiscover.netgroup.models import Netgroup

# Create your models here.
class Network(models.Model):
    """
    Network model class definition

    The model will contain the following info
    - Name
    - Description
    - NetID
    - Mask
    - Group
    """

    name = models.CharField(max_length=128)
    description = models.TextField(max_length=1024)
    netid = models.GenericIPAddressField()
    mask = models.GenericIPAddressField()
    group = models.ForeignKey(
        Netgroup, related_name="networks", on_delete=models.CASCADE, null=True)