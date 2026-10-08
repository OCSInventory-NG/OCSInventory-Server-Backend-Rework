from inventory.field.serializers import FieldSerializer
from inventory.section.serializers import SectionSerializer
from inventory.software.models import (
    DistroRelease,
    SoftwareDictionary,
    SoftwareMapping,
)
from inventory.template.serializers import TemplateSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class SoftwareMappingSerializer(ExpandableFieldsMixin, ModelSerializer):

    class Meta:
        model = SoftwareMapping
        fields = [
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
        expandable_fields = {
            "template": TemplateSerializer,
            "section": SectionSerializer,
            "name": FieldSerializer,
            "publisher": FieldSerializer,
            "version": FieldSerializer,
            "major_version": FieldSerializer,
            "minor_version": FieldSerializer,
            "patch_version": FieldSerializer,
            "architecture": FieldSerializer,
            "package_format": FieldSerializer,
            "source_package": FieldSerializer,
            "package_origin": FieldSerializer,
            "os_id": FieldSerializer,
            "os_like": FieldSerializer,
            "os_release": FieldSerializer,
            "os_codename": FieldSerializer,
            "running_kernel": FieldSerializer,
        }


class SoftwareDictionarySerializer(ModelSerializer):
    """Serialize aggregated asset/software relationships"""

    assets = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    installation_number = serializers.IntegerField(read_only=True)
    identity_status = serializers.CharField(
        source="identity.status", read_only=True, default=None
    )
    identity_product = serializers.CharField(
        source="identity.product", read_only=True, default=None
    )
    identity_identifier = serializers.CharField(
        source="identity.identifier", read_only=True, default=None
    )

    class Meta:
        model = SoftwareDictionary
        fields = [
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
            "assets",
            "updated_at",
            "installation_number",
            "identity_status",
            "identity_product",
            "identity_identifier",
        ]


class DistroReleaseSerializer(ModelSerializer):
    class Meta:
        model = DistroRelease
        fields = ["id", "base", "version", "codename"]
