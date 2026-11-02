from asset.asset_group.models import AssetGroup
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from security.models import (
    PRIORITY_CRITERIA,
    Exclusion,
    Exposure,
    SecuritySettings,
    Vulnerability,
)


class VulnerabilitySerializer(ModelSerializer):
    """Describes the model for the API schema; rows are built by security.reading."""

    class Meta:
        model = Vulnerability
        fields = [
            "id",
            "vuln_id",
            "summary",
            "published",
            "modified",
            "cvss_version",
            "cvss_vector",
            "cvss_score",
            "distro_rating",
            "kev",
            "kev_date_added",
            "epss",
            "epss_percentile",
            "url",
        ]
        read_only_fields = fields


class ExposureSerializer(ModelSerializer):
    """Describes the model for the API schema; rows are built by security.reading."""

    class Meta:
        model = Exposure
        fields = [
            "id",
            "asset",
            "vulnerability",
            "scheme",
            "product",
            "software_name",
            "version",
            "fixed_version",
            "fix_channel",
            "method",
            "uncertain",
            "first_seen",
            "last_seen",
            "closed_at",
            "resolution",
        ]
        read_only_fields = fields


class ExclusionSerializer(ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    active = serializers.SerializerMethodField()
    asset_name = serializers.CharField(source="asset.name", read_only=True, default="")
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    user_name = serializers.CharField(
        source="user.username", read_only=True, default=""
    )

    class Meta:
        model = Exclusion
        fields = [
            "id",
            "vuln_id",
            "asset",
            "asset_name",
            "group",
            "group_name",
            "comment",
            "expires_at",
            "user",
            "user_name",
            "created_at",
            "active",
        ]
        read_only_fields = [
            "asset_name",
            "group_name",
            "user",
            "user_name",
            "created_at",
            "active",
        ]

    def get_active(self, exclusion) -> bool:
        return exclusion.expires_at is None or exclusion.expires_at > timezone.now()

    def validate_comment(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("A comment is required")
        return value

    def validate_vuln_id(self, value):
        return (value or "").strip().upper()

    def validate_group(self, group):
        request = self.context.get("request")
        if group is not None and request is not None:
            if not AssetGroup.objects.visible_to(request.user).filter(pk=group.pk):
                raise serializers.ValidationError("Unknown group")
        return group

    def validate(self, attrs):
        asset = attrs.get("asset", getattr(self.instance, "asset", None))
        group = attrs.get("group", getattr(self.instance, "group", None))
        if (asset is None) == (group is None):
            raise serializers.ValidationError("A machine or a group, not both")
        expires_at = attrs.get("expires_at")
        if expires_at is not None and expires_at <= timezone.now():
            raise serializers.ValidationError({"expires_at": "A date to come"})
        return attrs


class SecuritySettingsSerializer(ModelSerializer):
    class Meta:
        model = SecuritySettings
        fields = [
            "id",
            "nvd_years",
            "priority",
            "cpe_match_score",
            "cpe_review_score",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate_nvd_years(self, value):
        if not 1 <= value <= 25:
            raise serializers.ValidationError("Between 1 and 25 years")
        return value

    def validate_priority(self, value):
        if (
            not isinstance(value, list)
            or not value
            or len(set(value)) != len(value)
            or any(criterion not in PRIORITY_CRITERIA for criterion in value)
        ):
            raise serializers.ValidationError(
                "Distinct criteria among " + ", ".join(PRIORITY_CRITERIA)
            )
        return value

    def validate(self, attrs):
        match = attrs.get(
            "cpe_match_score", getattr(self.instance, "cpe_match_score", 0.9)
        )
        review = attrs.get(
            "cpe_review_score", getattr(self.instance, "cpe_review_score", 0.5)
        )
        if not 0 < review < match <= 1:
            raise serializers.ValidationError("0 < review score < match score <= 1")
        return attrs
