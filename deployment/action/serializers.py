from rest_framework import serializers
from deployment.action.models import Action


class ActionSerializer(serializers.ModelSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Action
        fields = ["id", "package", "name", "priority", "date_created",
                  "action_type", "command", "file"]
        extra_kwargs = {"file": {"required": False}}
