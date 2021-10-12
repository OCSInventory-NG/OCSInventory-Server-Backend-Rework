from permission.permissions import DefaultModelPermissions
from ipdiscover.netdevice.models import Netdevice
from iipdiscover.netdevice.serializers import NetdeviceSerializer
from ocsinventory_backend.ocs_framework import viewsets


class NetdeviceViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Netdevice.objects.all()
    serializer_class = NetdeviceSerializer
    model = Netdevice