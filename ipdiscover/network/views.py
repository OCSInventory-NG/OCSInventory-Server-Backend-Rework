from ipdiscover.network.models import Network
from ipdiscover.network.serializers import NetworkSerializer
from permission.permissions import DefaultModelPermissions
from ocsinventory_backend.ocs_framework import viewsets


class NetworkViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Network.objects.all()
    serializer_class = NetworkSerializer
    model = Network
