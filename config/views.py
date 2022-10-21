from config.models import Config
from config.serializers import ConfigSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


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
