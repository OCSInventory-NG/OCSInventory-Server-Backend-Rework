from inventory.software.models import SoftwareDictionary, SoftwareMapping
from inventory.software.serializers import (
    SoftwareDictionarySerializer,
    SoftwareMappingSerializer,
)
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class SoftwareMappingViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]

    queryset = SoftwareMapping.objects.all()
    serializer_class = SoftwareMappingSerializer
    model = SoftwareMapping

    filterset_fields = [
        "id",
        "template",
        "section",
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
    ]


class SoftwareDictionaryViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]

    queryset = SoftwareDictionary.objects.all()
    serializer_class = SoftwareDictionarySerializer
    model = SoftwareDictionary
    search_fields = [
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
    ]
    ordering_fields = [
        "id",
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
        "installation_number",
    ]
    filterset_fields = [
        "id",
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
        "installation_number",
    ]
