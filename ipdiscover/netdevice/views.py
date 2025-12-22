from ipdiscover.netdevice.models import Netdevice
from ipdiscover.netdevice.serializers import NetdeviceSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter


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
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["ip", "netname", "mac", "last_seen"]
    ordering_fields = ["id", "ip", "netname", "mac", "network", "last_seen"]
