from config.models import Config
from config.serializers import ConfigSerializer, ServerInfoSerializer
from config.services import ServerInfoService
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.response import Response


class ConfigViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    # Set default filter
    filter_backends = []

    # No id for config overriding reconciliation_field
    reconciliation_field = "name"

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
    model = Config


class ServerInfoViewSet(viewsets.OCSViewSet):
    filter_backends = []
    permission_classes = [DefaultModelPermissions]
    queryset = Config.objects.all()
    serializer_class = ServerInfoSerializer
    model = Config
    http_method_names = ["get"]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(ServerInfoService.get_server_info())
        return Response(serializer.data, status=200)
