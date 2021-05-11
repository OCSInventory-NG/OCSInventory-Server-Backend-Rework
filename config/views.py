from rest_framework import viewsets
from permission.permissions import DefaultModelPermissions
from config.serializers import ConfigSerializer
from config.models import Config


class ConfigViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
