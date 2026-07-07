from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from django.db.models import F, Max
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from .models import (
    AssetEOLStatus, ComplianceResult, ComplianceRule,
    CustomEOLExtendedSupport, WindowsBuildMapping,
)


class ComplianceRuleSerializer(ModelSerializer):
    priority = serializers.IntegerField(required=False)

    class Meta:
        model = ComplianceRule
        fields = [
            "id",
            "priority",
            "name",
            "description",
            "type",
            "severity",
            "logic",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def _reorder_priorities(self, data):
        if "priority" not in data:
            return data

        priority = data["priority"]
        existing = ComplianceRule.objects.exclude(
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
            max_priority = ComplianceRule.objects.aggregate(Max("priority"))["priority__max"]
            validated_data["priority"] = (max_priority or 0) + 1
        else:
            self._reorder_priorities(validated_data)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "priority" in validated_data:
            self._reorder_priorities(validated_data)
        return super().update(instance, validated_data)


class AssetEOLStatusSerializer(ModelSerializer):
    asset_name = serializers.CharField(source="asset.name", read_only=True)

    class Meta:
        model = AssetEOLStatus
        fields = [
            "id", "asset", "asset_name",
            "product", "cycle", "eol", "is_eol",
            "support", "latest", "fetched_at",
        ]
        read_only_fields = ["id", "asset", "asset_name", "product", "cycle", "eol", "is_eol", "support", "latest", "fetched_at"]


class ComplianceResultSerializer(ExpandableFieldsMixin, ModelSerializer):
    asset_name = serializers.CharField(source="asset.name", read_only=True)

    class Meta:
        model = ComplianceResult
        fields = ["id", "asset", "asset_name", "rule", "status", "detail", "evaluated_at"]
        read_only_fields = ["evaluated_at", "asset_name"]
        expandable_fields = {
            "rule": ComplianceRuleSerializer,
        }


class WindowsBuildMappingSerializer(ModelSerializer):
    class Meta:
        model = WindowsBuildMapping
        fields = ["id", "build", "channel"]


class CustomEOLExtendedSupportSerializer(ModelSerializer):
    class Meta:
        model = CustomEOLExtendedSupport
        fields = ["id", "product", "cycle", "extended_support_until", "label"]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=CustomEOLExtendedSupport.objects.all(),
                fields=["product", "cycle"],
            )
        ]

    def validate_product(self, value):
        return value.lower().strip()

    def validate_cycle(self, value):
        return value.lower().strip()
