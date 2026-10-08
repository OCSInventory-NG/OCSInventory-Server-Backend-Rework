import re

from inventory.software_identity.models import (
    CpeProduct,
    IdentityDecision,
    PackageOrigin,
    SoftwareIdentity,
)
from inventory.software_identity.services import IdentityService
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class SoftwareIdentitySerializer(ModelSerializer):
    name = serializers.CharField(source="entry.name", read_only=True)

    class Meta:
        model = SoftwareIdentity
        fields = [
            "id",
            "entry",
            "name",
            "family",
            "match_key",
            "status",
            "reason",
            "scheme",
            "identifier",
            "product",
            "version",
            "score",
            "candidates",
            "decision",
            "index_version",
            "updated_at",
        ]
        read_only_fields = fields


class IdentityDecisionSerializer(ModelSerializer):
    class Meta:
        model = IdentityDecision
        fields = [
            "id",
            "family",
            "match_key",
            "product",
            "source",
            "user",
            "created_at",
        ]
        read_only_fields = ["source", "user", "created_at"]
        # A missing product must not record "no CPE": null has to be explicit
        extra_kwargs = {"product": {"required": True, "allow_null": True}}
        # decide() replaces an existing admin decision for the same key
        validators = []

    def validate_product(self, value):
        if value is None:
            return value
        vendor, _, product = value.partition(":")
        if not CpeProduct.objects.filter(vendor=vendor, product=product).exists():
            raise serializers.ValidationError("Unknown CPE product")
        return value

    def create(self, validated_data):
        return IdentityService.decide(
            validated_data["family"],
            validated_data["match_key"],
            validated_data.get("product"),
            validated_data.get("user"),
        )


class CpeProductSerializer(ModelSerializer):
    key = serializers.CharField(read_only=True)

    class Meta:
        model = CpeProduct
        fields = ["id", "vendor", "product", "key", "popularity"]


# The distribution is a purl namespace
DISTRIBUTION = re.compile(r"[a-z0-9][a-z0-9.-]*")


class PackageOriginSerializer(ModelSerializer):
    class Meta:
        model = PackageOrigin
        fields = ["id", "name", "distribution"]
        # Uniqueness is checked without case in validate_name
        validators = []

    def validate_name(self, value):
        value = value.strip()
        duplicates = PackageOrigin.objects.filter(name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("This origin already exists")
        return value

    def validate_distribution(self, value):
        value = value.strip().lower()
        if not DISTRIBUTION.fullmatch(value):
            raise serializers.ValidationError(
                "Lowercase letters, digits, dots and hyphens only"
            )
        return value
