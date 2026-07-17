import logging

from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AssetEOLStatus, ComplianceResult, ComplianceRule, ComplianceType,
    CustomEOLExtendedSupport, WindowsBuildMapping,
)
from .serializers import (
    AssetEOLStatusSerializer,
    ComplianceResultSerializer,
    ComplianceRuleSerializer,
    ComplianceTypeSerializer,
    CustomEOLExtendedSupportSerializer,
    WindowsBuildMappingSerializer,
)

LOGGER = logging.getLogger(__name__)


class ComplianceRuleViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = ComplianceRule.objects.all()
    serializer_class = ComplianceRuleSerializer
    model = ComplianceRule
    filterset_fields = ["type", "severity", "enabled"]
    search_fields = ["name", "description"]
    ordering_fields = ["id", "name", "enabled", "created_at"]

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="context-fields",
    )
    def context_fields(self, request):
        """
        Expose the compliance rule context schema for the rule editor.

        Mirrors automation's TriggerViewSet: returns the extra (non-model)
        context fields available to compliance rules — currently the software
        group — so the frontend builds the field list from the backend instead
        of hard-coding it.
        """
        from .context import resolver

        return Response(resolver.get_schema())


class ComplianceResultViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = ComplianceResult.objects.all()
    serializer_class = ComplianceResultSerializer
    model = ComplianceResult
    filterset_fields = ["asset", "rule", "status", "rule__severity"]
    search_fields = ["asset__name", "rule__name", "status"]
    ordering_fields = ["id", "evaluated_at", "status", "asset__name", "rule__name", "rule__severity"]

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="asset-summary",
    )
    def asset_summary(self, request):
        """
        Return aggregated compliance status per asset.

        GET /compliance/results/asset-summary/?asset__in=1,2,3

        Returns a list of {asset, global_status, counts} for each asset
        that has at least one compliance result. Assets with no results
        are not included (the frontend treats them as not_applicable).
        """
        asset_ids_param = request.query_params.get("asset__in")
        if asset_ids_param:
            try:
                asset_ids = [int(i) for i in asset_ids_param.split(",") if i.strip()]
            except ValueError:
                return Response({"error": "Invalid asset IDs"}, status=status.HTTP_400_BAD_REQUEST)
            queryset = ComplianceResult.objects.filter(asset_id__in=asset_ids).select_related("rule", "asset")
        else:
            queryset = ComplianceResult.objects.select_related("rule", "asset").all()

        summary = {}
        for result in queryset:
            asset_id = result.asset_id
            if asset_id not in summary:
                summary[asset_id] = {
                    "asset": asset_id,
                    "asset_name": result.asset.name if result.asset else None,
                    "counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                    "has_non_compliant": False,
                }
            if result.status == ComplianceResult.STATUS_NON_COMPLIANT and result.rule:
                summary[asset_id]["has_non_compliant"] = True
                sev = result.rule.severity
                if sev in summary[asset_id]["counts"]:
                    summary[asset_id]["counts"][sev] += 1

        result_list = [
            {
                "asset": data["asset"],
                "asset_name": data["asset_name"],
                "global_status": "non_compliant" if data["has_non_compliant"] else "compliant",
                "counts": data["counts"],
            }
            for data in summary.values()
        ]

        return Response(result_list)


class AssetEOLStatusViewSet(viewsets.OCSViewSet):
    """
    Read-only viewset exposing per-asset EOL status.

    GET /compliance/eol-status/
    """

    permission_classes = [DefaultModelPermissions]
    queryset = AssetEOLStatus.objects.select_related("asset").all()
    serializer_class = AssetEOLStatusSerializer
    model = AssetEOLStatus
    filterset_fields = {
        "is_eol":  ["exact"],
        "product": ["exact", "isnull"],
        "asset":   ["exact"],
    }
    search_fields = ["product", "asset__name"]
    ordering_fields = ["id", "asset", "is_eol", "product"]
    http_method_names = ["get", "head", "options"]

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="eol-summary",
    )
    def eol_summary(self, request):
        """
        Return EOL status for a set of assets.

        GET /compliance/eol-status/eol-summary/?asset__in=1,2,3
        """
        asset_ids_param = request.query_params.get("asset__in")
        if asset_ids_param:
            try:
                asset_ids = [int(i) for i in asset_ids_param.split(",") if i.strip()]
            except ValueError:
                return Response({"error": "Invalid asset IDs"}, status=status.HTTP_400_BAD_REQUEST)
            queryset = AssetEOLStatus.objects.filter(asset_id__in=asset_ids)
        else:
            queryset = AssetEOLStatus.objects.all()

        return Response([
            {
                "asset":   e.asset_id,
                "is_eol":  e.is_eol,
                "product": e.product,
                "cycle":   e.cycle,
                "eol":     e.eol,
            }
            for e in queryset
        ])


class ComplianceTypeViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = ComplianceType.objects.all()
    serializer_class = ComplianceTypeSerializer
    model = ComplianceType
    search_fields = ["name"]
    ordering_fields = ["id", "name"]


class WindowsBuildMappingViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = WindowsBuildMapping.objects.all()
    serializer_class = WindowsBuildMappingSerializer
    model = WindowsBuildMapping


class CustomEOLExtendedSupportViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = CustomEOLExtendedSupport.objects.all()
    serializer_class = CustomEOLExtendedSupportSerializer
    model = CustomEOLExtendedSupport
    filterset_fields = ["product", "cycle"]
    search_fields = ["product", "cycle"]
    ordering_fields = ["id", "product", "cycle"]
