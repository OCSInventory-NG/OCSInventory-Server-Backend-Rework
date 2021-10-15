from permission.permissions import DefaultModelPermissions
from ipdiscover.network.models import Network
from ipdiscover.network.serializers import NetworkSerializer
from rest_framework import viewsets


class NetworkViewSet(viewsets.ModelViewSet):
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