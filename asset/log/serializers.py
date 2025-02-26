from asset.log.models import Log
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class LogSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Log
        fields = [
            "id",
            "asset",
            "timestamp",
            "scope",
            "comment",
        ]
        extra_kwargs = {"timestamp": {"read_only": True}}
        http_method_names = ["get", "post"]
        expandable_fields = {}
