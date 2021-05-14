from rest_framework import viewsets
from permission.permissions import DefaultModelPermissions
from config.serializers import ConfigSerializer
from config.models import Config

# alias ocs_viewsets avoids conflict w/ rest_framework's imported viewsets
from ocsinventory_backend.ocs_framework import viewsets as ocs_viewsets


class ConfigViewSet(ocs_viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
    model = Config
