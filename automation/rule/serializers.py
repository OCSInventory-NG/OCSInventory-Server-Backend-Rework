from automation.rule.context import get_resolver_for_trigger
from automation.rule.models import Action, Rule
from django.contrib.contenttypes.models import ContentType
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class ActionSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
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


class RuleSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Rule
        fields = ["id", "description", "trigger", "enabled", "logic", "actions"]
        expandable_fields = {
            "actions": ActionSerializer,
        }

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        actions_data = validated_data.pop("actions", [])
        rule = super().create(validated_data)

        for action_data in actions_data:
            action_data["rule"] = rule
            Action.objects.create(**action_data)

        return rule


class TriggerSerializer(serializers.Serializer):
    trigger = serializers.CharField()
    model_name = serializers.CharField()
    action_targets = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )
    context_fields = serializers.SerializerMethodField()

    def get_context_fields(self, obj):
        trigger = obj.get("trigger")
        resolver = get_resolver_for_trigger(trigger)
        return resolver.get_schema()
