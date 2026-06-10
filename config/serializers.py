from config.models import Config
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class ConfigSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Config
        fields = ["name", "value"]
        expandable_fields = {}


class ServerInfoSerializer(serializers.Serializer):
    backend_version = serializers.CharField(allow_null=True)
    authentication_type = serializers.ListField(
        child=serializers.CharField(), allow_empty=True
    )
    infrastructure_type = serializers.CharField(allow_null=True)
    operating_system = serializers.CharField(allow_null=True)
    operating_system_version = serializers.CharField(allow_null=True)
    db_engine = serializers.CharField(allow_null=True)
    ocs_configuration = serializers.JSONField()
    python_version = serializers.CharField(allow_null=True)
    python_libs_version = serializers.DictField(
        child=serializers.CharField(allow_null=True), allow_empty=True
    )
