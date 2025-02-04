from automation.rule.models import Action, Rule
from django.contrib.contenttypes.models import ContentType
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class ActionSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Action
        fields = [
            "id",
            "rule",
            "description",
            "action",
            "field",
            "value",
            "content_type",
            "object_id",
            "object_slug",
        ]

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        if "object_slug" in validated_data.keys():
            content_type = validated_data.get("object_slug")
            app, model = content_type.split(".")
            ct = ContentType.objects.get_by_natural_key(app_label=app, model=model)

            validated_data["content_type"] = ct

        return super().create(validated_data)


class RuleSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Rule
        fields = ["id", "description", "trigger", "enabled", "logic", "actions"]
        expandable_fields = {
            "actions": {
                "serializer": "automation.rule.serializers.ActionSerializer",
                "many": True,
                "required": False,
            },
        }

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        if "actions" in validated_data.keys():
            # If actions are present
            actions = validated_data.pop("actions")
            parent = super().create(validated_data)

            for action in actions:
                action["rule"] = parent
            self.fields["actions"].create(actions)
        else:
            parent = super().create(validated_data)

        return parent
