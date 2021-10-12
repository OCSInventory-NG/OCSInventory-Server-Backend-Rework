from django.db import models

# Create your models here.
class Netdevice(models.Model):
    """
    Netdevice model class definition

    The model will contain the following info
    - IP
    - Netname
    - MAC
    - Lastupdate
    - Network
    """

    ip = models.GenericIPAddressField()
    netname = models.CharField(max_length=128)
    mac = models.CharField(max_length=20)
    network = models.ForeignKey(
        Template, related_name="netdevices", on_delete=models.CASCADE)
