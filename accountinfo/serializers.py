from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from django.contrib.contenttypes.models import ContentType
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class AccountinfoDataSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoData
        fields = ["id", "accountdata", "object_slug", "content_type", "object_id"]

        extra_kwargs = {"content_type": {"read_only": True}}
        expandable_fields = {}

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        content_type = validated_data.get("object_slug")
        app, model = content_type.split(".")
        ct = ContentType.objects.get_by_natural_key(app_label=app, model=model)

        validated_data["content_type"] = ct

        return super().create(validated_data)


class AccountinfoValueSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoValue
        fields = ["id", "accountinfo_config", "value"]
        expandable_fields = {}


class AccountinfoConfigSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoConfig
        fields = [
            "id",
            "name",
            "description",
            "datatype",
            "datatarget",
            "accountinfo_values",
        ]
        extra_kwargs = {"accountinfo_values": {"read_only": True}}

        expandable_fields = {
            "accountinfo_values": AccountinfoValueSerializer,
        }
