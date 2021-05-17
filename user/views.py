from django.contrib.auth.models import User
from rest_framework import viewsets, permissions
from permission.permissions import DefaultModelPermissions
from user.serializers import UserSerializer, MyAccountSerializer

# alias ocs_viewsets avoids conflict w/ rest_framework's imported viewsets
from ocsinventory_backend.ocs_framework import viewsets as ocs_viewsets


class UserViewSet(ocs_viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = User.objects.all()
    serializer_class = UserSerializer
    model = User


class MyAccountViewSet(viewsets.ModelViewSet):
    """This class will define the view behavior"""

    # Need to be authenticated to consult
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MyAccountSerializer
    http_method_names = ['get', 'patch']

    def get_queryset(self):
        """Query set get only the current connected user"""
        return User.objects.filter(username=self.request.user)
