from inventory.field.models import Field
from inventory.section.models import Section
from inventory.section.serializers import SectionExportSerializer, SectionSerializer
from inventory.template.models import Template, TemplateVersion
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import (
    ModelSerializer,
    PrimaryKeyRelatedField,
    SerializerMethodField,
)


class TemplateSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    sections = SectionSerializer(many=True, read_only=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Template
        fields = ["id", "name", "os", "is_protected", "last_update", "sections"]

        expandable_fields = {
            "sections": SectionSerializer,
        }
        extra_kwargs = {"last_update": {"read_only": True}}

    def create(self, validated_data):
        """Override create to allow nested creation of sections"""
        if "sections" in validated_data.keys():
            # If sections are present
            sections = validated_data.pop("sections")
            parent = super().create(validated_data)

            for section in sections:
                section["template"] = parent
            self.fields["sections"].create(sections)
        else:
            parent = super().create(validated_data)

        return parent


class TemplateExportSerializer(ModelSerializer):
    """
    Export serializer for Template, ids and fk relations are not included
    Nested values will always be expanded (no ExpandableFieldsMixin)
    """

    sections = SectionExportSerializer(many=True, read_only=False)

    class Meta:
        model = Template
        fields = ["name", "os", "is_protected", "sections"]


class FieldSnapshotSerializer(ModelSerializer):
    """
    Snapshot serializer for Field. Unlike FieldExportSerializer it keeps the
    primary key, so a rollback can match snapshot fields with the current ones
    by id and update them in place instead of recreating them (which would
    break saved searches / dynamic groups referencing those ids).
    """

    class Meta:
        model = Field
        fields = [
            "id",
            "name",
            "order",
            "retrieval_value",
            "override_target",
            "new_target",
            "retrieval_method",
            "retrieval_output",
            "options",
        ]


class SectionSnapshotSerializer(ModelSerializer):
    """Snapshot serializer for Section, keeping the primary key (see above)"""

    fields = FieldSnapshotSerializer(many=True)
    categories = PrimaryKeyRelatedField(
        source="category_set", many=True, read_only=True
    )

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "retrieval_method",
            "retrieval_output",
            "target",
            "fields",
            "options",
            "categories",
        ]


class TemplateSnapshotSerializer(ModelSerializer):
    """
    Snapshot serializer used by TemplateVersion. Keeps the primary keys of the
    template and its nested sections/fields so a rollback can restore by id.
    """

    sections = SectionSnapshotSerializer(many=True)

    class Meta:
        model = Template
        fields = ["id", "name", "os", "is_protected", "sections"]


class TemplateVersionListSerializer(ModelSerializer):
    """
    Lightweight serializer used to list a template's version history,
    the full snapshot is intentionally left out
    """

    created_by = SerializerMethodField()

    class Meta:
        model = TemplateVersion
        fields = ["id", "revision", "template", "created_at", "created_by", "label"]

    def get_created_by(self, obj):
        return obj.created_by.username if obj.created_by else None


class TemplateVersionSerializer(ModelSerializer):
    """
    Full serializer for a single version, snapshot included
    """

    created_by = SerializerMethodField()

    class Meta:
        model = TemplateVersion
        fields = [
            "id",
            "revision",
            "template",
            "created_at",
            "created_by",
            "label",
            "snapshot",
        ]
        extra_kwargs = {"snapshot": {"read_only": True}}

    def get_created_by(self, obj):
        return obj.created_by.username if obj.created_by else None
