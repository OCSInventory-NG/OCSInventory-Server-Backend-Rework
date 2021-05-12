from django.contrib.auth.models import User
from rest_framework import viewsets
from permission.permissions import DefaultModelPermissions
from user.serializers import UserSerializer, MyAccountSerializer
from rest_framework.permissions import IsAuthenticated


class UserViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = User.objects.all()
    serializer_class = UserSerializer


class MyAccountViewSet(viewsets.ModelViewSet):
    """ This class will define the view behavior """

    # Need to be authenticated to consult
    permission_classes = [IsAuthenticated]
    serializer_class = MyAccountSerializer
    http_method_names = ['get', 'patch']

    def get_queryset(self):
        """Query set get only the current connected user"""
        return User.objects.filter(username=self.request.user)
