from django.contrib.auth.models import Permission
from rest_framework import viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from permission.serializers import PermissionSerializer


class PermissionViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [IsAuthenticated]

    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    http_method_names = ['get']
