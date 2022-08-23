from django.contrib.auth.models import User
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import permissions
from rest_framework.response import Response
from user.serializers import MyAccountSerializer, UserSerializer


class UserViewSet(viewsets.OCSViewSet):
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


class MyAccountViewSet(viewsets.OCSViewSet):
    """This class will define the view behavior"""

    # Need to be authenticated to consult
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MyAccountSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        """Query set get only the current connected user"""
        return User.objects.filter(username=self.request.user)

    def list(self, request, *args, **kwargs):
        """Dedicated my account json response"""
        user = User.objects.filter(username=self.request.user).first()
        raw_permissions = user.get_all_permissions()
        refined_permissions = []

        # Remove the first part of the permission "object.permname"
        for permission in raw_permissions:
            splitted_permission = permission.split(".")
            refined_permissions.append(splitted_permission[1])

        reponse = {
            "id": getattr(user, "id", ""),
            "username": getattr(user, "username", ""),
            "email": getattr(user, "email", ""),
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
            "is_staff": getattr(user, "is_staff", False),
            "is_superuser": getattr(user, "is_superuser", False),
            "full_permissions": refined_permissions,
        }
        return Response(reponse)
