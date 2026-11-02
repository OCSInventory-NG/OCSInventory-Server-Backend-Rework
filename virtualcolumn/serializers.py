from group.serializers import GroupSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer, ValidationError
from user.serializers import UserSerializer
from virtualcolumn.models import ColumnLayout, VirtualCol


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


class ColumnLayoutSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    MAX_COLUMNS = 200
    MAX_KEY_LENGTH = 100

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = ColumnLayout
        fields = "__all__"
        # owner is set by the viewset, a client must not name it
        extra_kwargs = {
            "last_updated": {"read_only": True},
            "user": {"read_only": True},
            "columns": {"required": True},
        }
        expandable_fields = {"user": UserSerializer, "groups": GroupSerializer}

    def validate_columns(self, value):
        """
        Check the shape only, a key may name a column that is gone or not
        resolved yet, the client simply skips it
        """
        if not isinstance(value, list):
            raise ValidationError("Columns must be a list of column keys.")

        cleaned = []
        for key in value:
            if not isinstance(key, str) or not key.strip():
                raise ValidationError(f"Invalid column key: {key!r}")
            if len(key) > self.MAX_KEY_LENGTH:
                raise ValidationError(
                    f"Column key longer than {self.MAX_KEY_LENGTH} characters: {key!r}"
                )
            if key not in cleaned:
                cleaned.append(key)

        if not cleaned:
            raise ValidationError("A layout needs at least one column.")
        if len(cleaned) > self.MAX_COLUMNS:
            raise ValidationError(
                f"A layout cannot hold more than {self.MAX_COLUMNS} columns."
            )

        return cleaned
