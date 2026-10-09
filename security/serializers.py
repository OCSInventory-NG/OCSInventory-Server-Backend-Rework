from rest_framework.serializers import ModelSerializer
from security.models import Vulnerability


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
            "source",
            "url",
        ]
        read_only_fields = fields
