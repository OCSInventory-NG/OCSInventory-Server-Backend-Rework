from django.contrib.auth.models import Permission
from permission.serializers import PermissionSerializer
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


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
    http_method_names = ["get"]
