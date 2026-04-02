from django.contrib.contenttypes.models import ContentType
from notes.models import Note
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class NoteSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Note
        fields = [
            "id",
            "text",
            "creator",
            "created_at",
            "updated_at",
            "object_slug",
            "content_type",
            "object_id",
        ]
        extra_kwargs = {"content_type": {"read_only": True}}
        expandable_fields = {}

    def create(self, validated_data):
        """Override create to allow nested creation with object_slug"""
        object_slug = validated_data.get("object_slug")
        if object_slug:
            app, model = object_slug.split(".")
            ct = ContentType.objects.get_by_natural_key(app_label=app, model=model)
            validated_data["content_type"] = ct

        return super().create(validated_data)
