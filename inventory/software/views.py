from inventory.software.models import (
    DistroRelease,
    SoftwareDictionary,
    SoftwareMapping,
)
from inventory.software.serializers import (
    DistroReleaseSerializer,
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
        "architecture",
        "package_format",
        "source_package",
        "package_origin",
        "os_id",
        "os_like",
        "os_release",
        "os_codename",
        "running_kernel",
    ]


class SoftwareDictionaryViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]

    queryset = SoftwareDictionary.objects.select_related("identity")
    serializer_class = SoftwareDictionarySerializer
    model = SoftwareDictionary
    search_fields = [
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
        "platform_key",
        "source_package",
        "package_origin",
    ]
    ordering_fields = [
        "id",
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
        "platform_family",
        "platform_key",
        "architecture",
        "package_format",
        "source_package",
        "package_origin",
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
        "platform_family",
        "platform_key",
        "architecture",
        "package_format",
        "source_package",
        "package_origin",
        "installation_number",
        "identity__status",
    ]


class DistroReleaseViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = DistroRelease.objects.all()
    serializer_class = DistroReleaseSerializer
    model = DistroRelease
    filterset_fields = ["id", "base", "version", "codename"]
