from django.db import models
from ipdiscover.network.models import Network

# Create your models here.


class Netdevice(models.Model):
    """
    Netdevice model class definition

    The model will contain the following info
    - IP
    - Netname
    - MAC
    - Network
    - Last seen
    """

    ip = models.GenericIPAddressField()
    netname = models.CharField(max_length=128)
    mac = models.CharField(max_length=20)
    network = models.ForeignKey(
        Network, related_name="netdevices", on_delete=models.CASCADE
    )
    last_seen = models.DateTimeField(auto_now=True)
