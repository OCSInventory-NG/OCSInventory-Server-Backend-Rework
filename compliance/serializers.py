from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from .models import (
    AssetEOLStatus, ComplianceResult, ComplianceRule, ComplianceType,
    CustomEOLExtendedSupport, WindowsBuildMapping,
)


class ComplianceTypeSerializer(ModelSerializer):
    class Meta:
        model = ComplianceType
        fields = ["id", "name"]


class ComplianceRuleSerializer(ModelSerializer):
    class Meta:
        model = ComplianceRule
        fields = [
            "id",
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
        fields = ["id", "product", "cycle", "is_extended"]
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
