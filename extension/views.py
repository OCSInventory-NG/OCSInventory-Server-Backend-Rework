from django_filters.rest_framework import DjangoFilterBackend
from extension.models import Extension
from extension.serializers import ExtensionSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter


class ExtensionViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Extension.objects.all()
    serializer_class = ExtensionSerializer
    model = Extension
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description", "version", "author", "enabled"]
    ordering_fields = ["id", "name", "description", "version", "author", "enabled"]
    filterset_fields = ["name", "description", "version", "author", "enabled"]
