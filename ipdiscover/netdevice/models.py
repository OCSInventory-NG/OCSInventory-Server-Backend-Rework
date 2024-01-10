from django.db import models
from ipdiscover.network.models import Network
from django.dispatch import receiver
from django.db.models.signals import post_save
from automation.rule.logic import Logic

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

@receiver(post_save, sender=Netdevice)
def netdevice_received_handler(sender, instance, created, **kwargs):
    print("netdevice_received_handler")
    if not getattr(instance, 'processed', False):
        logic = Logic('netdevice_received', instance)
        instance = logic.process_rules()
