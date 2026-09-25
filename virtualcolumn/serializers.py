from group.serializers import GroupSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer, ValidationError
from user.serializers import UserSerializer
from virtualcolumn.models import VirtualCol


class VirtualColSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = VirtualCol
        fields = "__all__"
        # owner is set by the viewset, a client must not name it
        extra_kwargs = {
            "last_updated": {"read_only": True},
            "user": {"read_only": True},
        }
        expandable_fields = {"user": UserSerializer, "groups": GroupSerializer}

    def validate_mapping(self, value):
        """Check the shape only, what the admin maps together is their call"""
        if not isinstance(value, dict):
            raise ValidationError("Mapping must be an object keyed by template id.")

        cleaned = {}
        for template_id, field_id in value.items():
            if field_id in (None, ""):
                continue
            try:
                cleaned[str(int(template_id))] = int(field_id)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"Invalid mapping entry: {template_id!r} -> {field_id!r}"
                )

        return cleaned
