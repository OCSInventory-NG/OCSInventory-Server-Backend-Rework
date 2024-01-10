from automation.rule.models import Action, Rule
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers


class ActionSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Action
        fields = [
            "id",
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


class RuleSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    actions = ActionSerializer(many=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Rule
        fields = ["id", "description", "trigger", "enabled", "logic", "actions"]

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        if "actions" in validated_data.keys():
            actions = validated_data.pop("actions")

        parent = super().create(validated_data)

        # create actions
        if actions:
            for action in actions:
                action["rule"] = parent
            self.fields["actions"].create(actions)

        return parent
