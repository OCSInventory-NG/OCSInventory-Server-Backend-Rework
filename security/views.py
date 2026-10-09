from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from security import reading
from security.models import Vulnerability
from security.serializers import VulnerabilitySerializer

READ_ONLY = ["get", "head", "options"]
FAMILIES = ("deb", "rpm", "windows", "macos")


def _asset(params):
    value = params.get("asset")
    if value in (None, ""):
        return None
    if not value.isdecimal() or not value.isascii():
        raise ValidationError({"asset": "A machine id"})
    return int(value)


class VulnerabilityViewSet(viewsets.OCSViewSet):
    """
    Vulnerabilities of the fleet's identified software. Rows are computed from
    the findings and the machines, not read from one table.
    """

    permission_classes = [DefaultModelPermissions]
    http_method_names = READ_ONLY
    queryset = Vulnerability.objects.all()
    serializer_class = VulnerabilitySerializer
    model = Vulnerability
    filterset_fields = ["vuln_id", "source"]
    lookup_field = "vuln_id"
    lookup_value_regex = "[^/]+"

    def list(self, request, *args, **kwargs):
        params = request.query_params
        level = params.get("level") or None
        if level is not None and level not in reading.LEVELS:
            raise ValidationError({"level": ", ".join(reading.LEVELS)})
        fix = params.get("fix") or None
        if fix not in (None, "yes", "no"):
            raise ValidationError({"fix": "yes or no"})
        family = params.get("family") or None
        if family is not None and family not in FAMILIES:
            raise ValidationError({"family": ", ".join(FAMILIES)})
        ordering = params.get("ordering") or "-cvss_score"
        if ordering not in reading.ORDERINGS:
            raise ValidationError({"ordering": ", ".join(reading.ORDERINGS)})
        rows = reading.vulnerability_rows(
            level_filter=level,
            fix=None if fix is None else fix == "yes",
            family=family,
            asset_id=_asset(params),
            search=params.get("search", ""),
            ordering=ordering,
        )
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(rows)

    def retrieve(self, request, *args, **kwargs):
        return Response(reading.vulnerability_detail(self.get_object()))

    @action(detail=False, methods=["get"])
    def coverage(self, request):
        return Response(reading.coverage(_asset(request.query_params)))
