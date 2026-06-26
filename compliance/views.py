import csv
import io
import json
import logging

from django.db.models import Max
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AssetEOLStatus, ComplianceResult, ComplianceRule, ComplianceTarget, WindowsBuildMapping
from .serializers import (
    AssetEOLStatusSerializer,
    ComplianceResultSerializer,
    ComplianceRuleSerializer,
    ComplianceTargetSerializer,
    WindowsBuildMappingSerializer,
)

LOGGER = logging.getLogger(__name__)

_IMPORT_REQUIRED = {"name", "type", "severity", "logic"}
_IMPORT_OPTIONAL = {"description", "enabled"}
_VALID_TYPES     = {c[0] for c in ComplianceRule.TYPE_CHOICES}
_VALID_SEVERITIES = {c[0] for c in ComplianceRule.SEVERITY_CHOICES}


class ComplianceRuleViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior for ComplianceRule

    Args:
        viewsets ([OCSViewSet])
    """

    permission_classes = [DefaultModelPermissions]
    queryset = ComplianceRule.objects.all()
    serializer_class = ComplianceRuleSerializer
    model = ComplianceRule
    filterset_fields = ["type", "severity", "enabled"]
    search_fields = ["name", "description"]
    ordering_fields = ["id", "priority", "name", "enabled", "created_at"]

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser],
        url_path="import",
    )
    def import_csv(self, request):
        """
        Import compliance rules from a CSV file.

        Expected format (semicolon-separated, UTF-8):
            name;description;type;severity;logic;enabled

        - logic  : valid JSON string
        - enabled: true/false (optional, defaults to true)
        - Rows with unknown type or severity are skipped.

        POST /compliance/rules/import/
        """
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "Aucun fichier fourni."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created, updated, skipped, errors = [], [], [], []

        try:
            text = file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text), delimiter=";")

            for i, row in enumerate(reader, start=2):
                row = {k.strip(): v.strip() for k, v in row.items() if k}

                missing = _IMPORT_REQUIRED - row.keys()
                if missing:
                    errors.append({"row": i, "error": f"Colonnes manquantes : {missing}"})
                    skipped.append(i)
                    continue

                name     = row["name"]
                type_    = row["type"]
                severity = row["severity"]
                enabled  = row.get("enabled", "true").lower() not in ("false", "0", "")

                if type_ not in _VALID_TYPES:
                    errors.append({"row": i, "error": f"Type invalide : {type_!r}"})
                    skipped.append(i)
                    continue

                if severity not in _VALID_SEVERITIES:
                    errors.append({"row": i, "error": f"Sévérité invalide : {severity!r}"})
                    skipped.append(i)
                    continue

                try:
                    logic = json.loads(row["logic"])
                except json.JSONDecodeError as exc:
                    errors.append({"row": i, "error": f"Logic JSON invalide : {exc}"})
                    skipped.append(i)
                    continue

                defaults = {
                    "description": row.get("description") or None,
                    "type":        type_,
                    "severity":    severity,
                    "logic":       logic,
                    "enabled":     enabled,
                }
                rule = ComplianceRule.objects.filter(name=name).first()
                if rule:
                    for field, value in defaults.items():
                        setattr(rule, field, value)
                    rule.save(update_fields=list(defaults.keys()))
                    updated.append(rule.name)
                else:
                    max_priority = ComplianceRule.objects.aggregate(Max("priority"))["priority__max"]
                    defaults["priority"] = (max_priority or 0) + 1
                    rule = ComplianceRule.objects.create(name=name, **defaults)
                    created.append(rule.name)

        except Exception as exc:
            LOGGER.exception("CSV import failed")
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "created": len(created),
            "updated": len(updated),
            "skipped": len(skipped),
            "errors":  errors,
            "rules":   created,
        }, status=status.HTTP_200_OK)


class ComplianceTargetViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior for ComplianceTarget

    Args:
        viewsets ([OCSViewSet])
    """

    permission_classes = [DefaultModelPermissions]
    queryset = ComplianceTarget.objects.all()
    serializer_class = ComplianceTargetSerializer
    model = ComplianceTarget
    filterset_fields = ["rule", "target_type"]
    ordering_fields = ["id", "rule", "target_type"]


class ComplianceResultViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior for ComplianceResult

    Args:
        viewsets ([OCSViewSet])
    """

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
            queryset = ComplianceResult.objects.filter(asset_id__in=asset_ids).select_related("rule")
        else:
            queryset = ComplianceResult.objects.select_related("rule").all()

        summary = {}
        for result in queryset:
            asset_id = result.asset_id
            if asset_id not in summary:
                summary[asset_id] = {
                    "asset": asset_id,
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
                "global_status": "non_compliant" if data["has_non_compliant"] else "compliant",
                "counts": data["counts"],
            }
            for data in summary.values()
        ]

        return Response(result_list)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated],
        url_path="evaluate",
    )
    def evaluate(self, request):
        """
        Trigger a full compliance evaluation.

        Evaluates all enabled rules against all assets and persists the
        results. Returns a summary of what was evaluated.

        POST /compliance/results/evaluate/
        """
        from .engine import run_evaluation

        report = run_evaluation()
        return Response({
            "evaluated": len(report),
            "results": report,
        })


class AssetEOLStatusViewSet(viewsets.OCSViewSet):
    """
    Read-only viewset exposing per-asset EOL status.

    Populated automatically at each inventory — no user action required.

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


class WindowsBuildMappingViewSet(viewsets.OCSViewSet):
    """
    CRUD viewset for the Windows build → channel mapping table.

    GET/POST /compliance/windows-build-mapping/
    PATCH/DELETE /compliance/windows-build-mapping/{id}/
    """

    permission_classes = [DefaultModelPermissions]
    queryset = WindowsBuildMapping.objects.all()
    serializer_class = WindowsBuildMappingSerializer
    model = WindowsBuildMapping
