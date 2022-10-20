from ipdiscover.netgroup.models import Netgroup
from ipdiscover.netgroup.serializers import NetgroupSerializer
from permission.permissions import DefaultModelPermissions
from ocsinventory_backend.ocs_framework import viewsets


class NetgroupViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Netgroup.objects.all()
    serializer_class = NetgroupSerializer
    model = Netgroup
