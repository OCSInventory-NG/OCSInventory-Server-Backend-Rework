from django.db.models import Q
from django.utils import timezone
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from security import reading
from security.config import PRIORITY_CRITERIA
from security.models import (
    Exclusion,
    Exposure,
    Vulnerability,
)
from security.serializers import (
    ExclusionSerializer,
    ExposureSerializer,
    VulnerabilitySerializer,
)

READ_ONLY = ["get", "head", "options"]
FAMILIES = ("deb", "rpm", "windows", "macos")


def _asset(params, required=False):
    value = params.get("asset")
    if value in (None, ""):
        if required:
            raise ValidationError({"asset": "A machine id"})
        return None
    if not value.isdecimal() or not value.isascii():
        raise ValidationError({"asset": "A machine id"})
    return int(value)


def _choice(params, name, choices):
    value = params.get(name) or None
    if value is not None and value not in choices:
        raise ValidationError({name: ", ".join(choices)})
    return value


def _yes_no(params, name):
    value = _choice(params, name, ("yes", "no"))
    return None if value is None else value == "yes"


def _list(params, name, choices):
    values = [v.strip() for v in (params.get(name) or "").split(",") if v.strip()]
    if any(value not in choices for value in values) or len(set(values)) != len(values):
        raise ValidationError({name: "Comma separated, among " + ", ".join(choices)})
    return values


def _filters(params):
    """The filters of the vulnerability list, shared by its summary."""
    return {
        "level_filter": _choice(params, "level", reading.LEVELS),
        "fix": _yes_no(params, "fix"),
        "family": _choice(params, "family", FAMILIES),
        "asset_id": _asset(params),
        "search": params.get("search", ""),
        "kev": _yes_no(params, "kev"),
        "show": _list(params, "show", reading.NOISE),
    }


class VulnerabilityViewSet(viewsets.OCSViewSet):
    """
    Vulnerabilities open on the fleet's machines, from their exposures,
    exclusions applied, in the active priority order.
    """

    permission_classes = [DefaultModelPermissions]
    http_method_names = READ_ONLY
    queryset = Vulnerability.objects.all()
    serializer_class = VulnerabilitySerializer
    model = Vulnerability
    filterset_fields = ["vuln_id"]
    lookup_field = "vuln_id"
    lookup_value_regex = "[^/]+"

    def list(self, request, *args, **kwargs):
        params = request.query_params
        rows, hidden, order = reading.vulnerability_rows(
            ordering=_list(params, "ordering", PRIORITY_CRITERIA) or None,
            **_filters(params),
        )
        page = self.paginate_queryset(rows)
        if page is not None:
            response = self.get_paginated_response(page)
        else:
            response = Response({"count": len(rows), "results": rows})
        response.data["ordering"] = order
        response.data["hidden"] = hidden
        return response

    def retrieve(self, request, *args, **kwargs):
        return Response(reading.vulnerability_detail(self.get_object()))

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Totals of the list with the same filters, in one request."""
        return Response(reading.vulnerability_summary(**_filters(request.query_params)))

    @action(detail=False, methods=["get"])
    def coverage(self, request):
        return Response(reading.coverage(_asset(request.query_params)))

    @action(detail=False, methods=["get"])
    def machines(self, request):
        """
        The machines with their coverage, the machines not covered first:
        status, reason and family filters.
        """
        params = request.query_params
        status = _choice(params, "status", reading.MACHINE_STATUSES)
        reason = _choice(params, "reason", reading.NOT_COVERED_REASONS)
        rows = reading.machine_rows(family=_choice(params, "family", FAMILIES))
        rows = [
            row
            for row in rows
            if (status is None or row["status"] == status)
            and (reason is None or row["reason"] == reason)
        ]
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(page)
        return Response({"count": len(rows), "results": rows})

    @action(detail=False, methods=["get"])
    def sources(self, request):
        return Response(reading.sources())


class ExposureViewSet(viewsets.OCSViewSet):
    """A machine's exposures, open or closed, and the state of its software."""

    permission_classes = [DefaultModelPermissions]
    http_method_names = READ_ONLY
    queryset = Exposure.objects.all()
    serializer_class = ExposureSerializer
    model = Exposure
    filterset_fields = ["asset", "vulnerability", "resolution"]

    def list(self, request, *args, **kwargs):
        params = request.query_params
        rows = reading.asset_exposures(
            _asset(params, required=True),
            status=_choice(params, "status", ("open", "closed", "all")) or "open",
        )
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(rows)

    @action(detail=False, methods=["get"])
    def software(self, request):
        """The software of a machine with the state of each installation."""
        rows = reading.asset_software_states(_asset(request.query_params, True))
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(rows)


class ExclusionViewSet(viewsets.OCSViewSet):
    """Exclusions; ?active=true|false keeps those in force, or the expired ones."""

    permission_classes = [DefaultModelPermissions]
    queryset = Exclusion.objects.select_related("asset", "group", "user")
    serializer_class = ExclusionSerializer
    model = Exclusion
    filterset_fields = ["id", "vuln_id", "asset", "group", "user"]
    search_fields = ["vuln_id", "comment"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        active = _choice(self.request.query_params, "active", ("true", "false"))
        if active is None:
            return queryset
        in_force = Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        return (
            queryset.filter(in_force)
            if active == "true"
            else queryset.exclude(in_force)
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
