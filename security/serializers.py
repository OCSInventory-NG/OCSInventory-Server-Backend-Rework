from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from .models import CpeMatch, CveReport
from .services import build_cve_url, installed_version_display


class CpeMatchSerializer(ModelSerializer):
    software_name = serializers.CharField(source="software.name", read_only=True)
    software_publisher = serializers.CharField(
        source="software.publisher", read_only=True
    )

    class Meta:
        model = CpeMatch
        fields = [
            "id",
            "software",
            "software_name",
            "software_publisher",
            "cpe",
            "cpe_rank",
            "source",
            "status",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "software_name",
            "software_publisher",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]


class CveReportSerializer(ModelSerializer):
    software_name = serializers.CharField(source="software.name", read_only=True)
    software_publisher = serializers.CharField(
        source="software.publisher", read_only=True
    )
    software_version = serializers.SerializerMethodField()
    cve_url = serializers.SerializerMethodField()
    impacted_asset_count = serializers.IntegerField(
        source="software.installation_number", read_only=True
    )

    class Meta:
        model = CveReport
        fields = [
            "id",
            "software",
            "software_name",
            "software_publisher",
            "software_version",
            "cve_id",
            "cve_url",
            "cvss_score",
            "published_date",
            "version_match",
            "fetched_at",
            "impacted_asset_count",
        ]
        read_only_fields = fields

    def get_software_version(self, obj):
        return installed_version_display(obj.software)

    def get_cve_url(self, obj):
        if not self.context.get("show_cve_url", True):
            return None
        return build_cve_url(obj.cve_id)
