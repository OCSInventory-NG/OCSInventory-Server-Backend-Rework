from automation.rule.context import get_resolver_for_trigger
from automation.rule.models import Action, Rule
from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Max
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class ActionSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    priority = serializers.IntegerField(required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Action
        fields = [
            "id",
            "rule",
            "priority",
            "description",
            "action",
            "field",
            "value",
        ]

    def custom_validate(self, data):
        rule = data.get("rule") or (self.instance.rule if self.instance else None)
        if rule is None or "priority" not in data:
            return data

        priority = data["priority"]
        existing = Action.objects.filter(rule=rule).exclude(
            pk=self.instance.pk if self.instance else None
        )

        if self.instance:
            if priority < self.instance.priority:
                existing.filter(
                    priority__lt=self.instance.priority,
                    priority__gte=priority,
                ).update(priority=F("priority") + 1)
            elif priority > self.instance.priority:
                existing.filter(
                    priority__lte=priority,
                    priority__gt=self.instance.priority,
                ).update(priority=F("priority") - 1)
        else:
            existing.filter(priority__gte=priority).update(priority=F("priority") + 1)

        return data

    def create(self, validated_data):
        if "priority" not in validated_data:
            validated_data["priority"] = (
                Action.objects.filter(rule=validated_data["rule"]).count() + 1
            )
        else:
            self.custom_validate(validated_data)

        if "object_slug" in validated_data.keys():
            content_type = validated_data.get("object_slug")
            app, model = content_type.split(".")
            ct = ContentType.objects.get_by_natural_key(app_label=app, model=model)

            validated_data["content_type"] = ct

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "priority" in validated_data:
            self.custom_validate(validated_data)

        if "object_slug" in validated_data.keys():
            content_type = validated_data.get("object_slug")
            app, model = content_type.split(".")
            ct = ContentType.objects.get_by_natural_key(app_label=app, model=model)

            validated_data["content_type"] = ct

        return super().update(instance, validated_data)


class RuleSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    priority = serializers.IntegerField(required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Rule
        fields = [
            "id",
            "priority",
            "description",
            "trigger",
            "enabled",
            "logic",
            "break_on_match",
            "actions",
        ]
        expandable_fields = {
            "actions": ActionSerializer,
        }

    def custom_validate(self, data):
        if "priority" not in data:
            return data

        trigger = data.get("trigger") or (
            self.instance.trigger if self.instance else None
        )
        if trigger is None:
            return data

        priority = data["priority"]
        existing = Rule.objects.filter(trigger=trigger).exclude(
            pk=self.instance.pk if self.instance else None
        )

        if self.instance:
            if priority < self.instance.priority:
                existing.filter(
                    priority__lt=self.instance.priority,
                    priority__gte=priority,
                ).update(priority=F("priority") + 1)
            elif priority > self.instance.priority:
                existing.filter(
                    priority__lte=priority,
                    priority__gt=self.instance.priority,
                ).update(priority=F("priority") - 1)
        else:
            existing.filter(priority__gte=priority).update(priority=F("priority") + 1)

        return data

    def create(self, validated_data):
        actions_data = validated_data.pop("actions", [])

        if "priority" not in validated_data:
            max_priority = Rule.objects.filter(
                trigger=validated_data["trigger"]
            ).aggregate(Max("priority"))["priority__max"]
            validated_data["priority"] = (max_priority or 0) + 1
        else:
            self.custom_validate(validated_data)

        rule = super().create(validated_data)

        for action_data in actions_data:
            action_data["rule"] = rule
            Action.objects.create(**action_data)

        return rule

    def update(self, instance, validated_data):
        if "priority" in validated_data:
            self.custom_validate(validated_data)
        return super().update(instance, validated_data)


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
