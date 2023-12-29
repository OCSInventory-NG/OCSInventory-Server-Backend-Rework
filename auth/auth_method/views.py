from auth.auth_method.models import AuthMethod
from auth.auth_method.serializers import AuthMethodSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class AuthMethodViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # TODO : permissions ?
    permission_classes = [DefaultModelPermissions]

    queryset = AuthMethod.objects.all()
    serializer_class = AuthMethodSerializer
    model = AuthMethod
