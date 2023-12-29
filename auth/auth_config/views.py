from auth.auth_config.models import AuthConfig
from auth.auth_config.serializers import AuthConfigSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class AuthConfigViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # TODO : permissions ?
    permission_classes = [DefaultModelPermissions]

    queryset = AuthConfig.objects.all()
    serializer_class = AuthConfigSerializer
    model = AuthConfig

    filterset_fields = ['id', 'auth_method', 'priority', 'enabled']
