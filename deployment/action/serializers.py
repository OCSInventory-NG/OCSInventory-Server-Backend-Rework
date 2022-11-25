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
        # re-add 'file' field when django-filters issue is fixed
        # fields = ["id", "package_id", "name", "priority", "date_created",
        # "action_type", "command", "file", "output"]
        fields = ["id", "package_id", "name", "priority", "date_created", "action_type",
                  "command", "output"]
        extra_kwargs = {"package_id": {"required": False},
                        "file": {"required": False},
                        "output": {"required": False}}
