import logging

from django.utils import timezone
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .config import get_cve_config
from .models import CpeMatch, CveReport
from .serializers import CpeMatchSerializer, CveReportSerializer
from .services import build_cve_summary, fetch_and_store_cves

LOGGER = logging.getLogger(__name__)


class CpeMatchViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = CpeMatch.objects.select_related("software").all()
    serializer_class = CpeMatchSerializer
    model = CpeMatch
    filterset_fields = ["status", "source"]
    search_fields = ["software__name", "software__publisher", "cpe"]
    ordering_fields = ["id", "updated_at", "status", "cpe_rank"]

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """
        Human review decision on a pending CPE match.

        POST body: {"decision": "confirm"|"reject"}
        """
        decision = request.data.get("decision")
        if decision not in ("confirm", "reject"):
            return Response(
                {"error": "decision must be 'confirm' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cpe_match = self._apply_review(self.get_object(), decision, request.user)
        return Response(CpeMatchSerializer(cpe_match).data)

    @action(detail=False, methods=["post"], url_path="bulk-review")
    def bulk_review(self, request):
        """
        Human review decision applied to several CPE matches at once.

        POST body: {"ids": [1, 2, 3], "decision": "confirm"|"reject"}
        """
        decision = request.data.get("decision")
        if decision not in ("confirm", "reject"):
            return Response(
                {"error": "decision must be 'confirm' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": "ids must be a non-empty list"}, status=status.HTTP_400_BAD_REQUEST
            )

        cpe_matches = list(self.get_queryset().filter(id__in=ids))
        found_ids = {cpe_match.id for cpe_match in cpe_matches}
        missing_ids = [id for id in ids if id not in found_ids]

        for cpe_match in cpe_matches:
            self._apply_review(cpe_match, decision, request.user)

        return Response(
            {
                "updated": CpeMatchSerializer(cpe_matches, many=True).data,
                "missing_ids": missing_ids,
            }
        )

    def _apply_review(self, cpe_match, decision, user):
        cpe_match.status = (
            CpeMatch.STATUS_CONFIRMED if decision == "confirm" else CpeMatch.STATUS_REJECTED
        )
        cpe_match.reviewed_by = user if user.is_authenticated else None
        cpe_match.reviewed_at = timezone.now()
        cpe_match.save()

        if cpe_match.status == CpeMatch.STATUS_CONFIRMED and cpe_match.cpe:
            fetch_and_store_cves(cpe_match.software, cpe_match.cpe)

        return cpe_match

    @action(detail=True, methods=["post"], url_path="set-manual-cpe")
    def set_manual_cpe(self, request, pk=None):
        """
        Force a manual CPE for this software.

        POST body: {"cpe": "cpe:2.3:a:..."}
        """
        cpe_match = self.get_object()
        cpe = request.data.get("cpe")
        if not cpe:
            return Response(
                {"error": "cpe is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        cpe_match.cpe = cpe
        cpe_match.cpe_rank = None
        cpe_match.source = CpeMatch.SOURCE_MANUAL
        cpe_match.status = CpeMatch.STATUS_CONFIRMED
        cpe_match.reviewed_by = request.user if request.user.is_authenticated else None
        cpe_match.reviewed_at = timezone.now()
        cpe_match.save()

        fetch_and_store_cves(cpe_match.software, cpe)

        return Response(CpeMatchSerializer(cpe_match).data)


class CveReportViewSet(viewsets.OCSViewSet):
    """
    Read-only viewset exposing CVE reports.

    GET /security/cve-reports/
    """

    permission_classes = [DefaultModelPermissions]
    queryset = CveReport.objects.select_related("software").order_by(
        "-cvss_score", "-software__installation_number"
    )
    serializer_class = CveReportSerializer
    model = CveReport
    filterset_fields = ["software", "cvss_score", "version_match"]
    search_fields = ["cve_id", "software__name"]
    ordering_fields = ["id", "cvss_score", "published_date", "fetched_at"]
    ordering = ["-cvss_score", "-software__installation_number"]
    http_method_names = ["get", "head", "options"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["show_cve_url"] = get_cve_config()["show_cve_url"]
        return context

    @action(detail=False, methods=["get"], url_path="by-asset/(?P<asset_id>[^/.]+)")
    def by_asset(self, request, asset_id=None):
        """
        Return CVE reports for all software installed on a given asset.

        GET /security/cve-reports/by-asset/<asset_id>/
        """
        queryset = self.get_queryset().filter(software__assets__id=asset_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """
        Aggregated counts for dashboard tiles: CVE counts by CVSS severity
        bucket, distinct CVE/software/asset counts, and the highest CVSS
        score currently known.

        GET /security/cve-reports/summary/
        """
        return Response(build_cve_summary(self.get_queryset()))
