from deployment.action.models import DeploymentAction
from rest_framework import serializers


class ActionSerializer(serializers.ModelSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = DeploymentAction
        fields = [
            "id",
            "package",
            "name",
            "priority",
            "date_created",
            "action_type",
            "command",
            "file",
            "original_file_name",
        ]
        extra_kwargs = {
            "file": {"required": False},
            "original_file_name": {"required": False}
        }
