from inventory.field.serializers import FieldSerializer
from inventory.section.serializers import SectionSerializer
from inventory.software.models import SoftwareDictionary, SoftwareMapping
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
        }


class SoftwareDictionarySerializer(ModelSerializer):
    """Serialize aggregated asset/software relationships"""

    assets = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

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
            "assets",
            "updated_at",
        ]
