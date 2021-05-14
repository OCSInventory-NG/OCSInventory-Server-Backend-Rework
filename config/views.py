from rest_framework import viewsets
from permission.permissions import DefaultModelPermissions
from config.serializers import ConfigSerializer
from config.models import Config

from ocsinventory_backend.bulk_processing import ocs_views


class ConfigViewSet(ocs_views.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
    model = Config
    uniq_field = 'username'
