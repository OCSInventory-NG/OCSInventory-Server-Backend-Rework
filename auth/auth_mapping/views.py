from auth.auth_mapping.models import AuthMapping
from auth.auth_mapping.serializers import AuthMappingSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class AuthMappingViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # TODO : permissions ?
    permission_classes = [DefaultModelPermissions]

    queryset = AuthMapping.objects.all()
    serializer_class = AuthMappingSerializer
    model = AuthMapping
