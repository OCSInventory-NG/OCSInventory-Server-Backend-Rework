from asset.inventory_base.models import InventoryBase
from django.db.models import Count, Min, Q, Sum
from inventory.software.models import SoftwareDictionary
from inventory.software_identity.models import (
    CpeIndexState,
    CpeProduct,
    IdentityDecision,
    PackageOrigin,
    SoftwareIdentity,
)
from inventory.software_identity.normalizers.base import MATCHED, REVIEW
from inventory.software_identity.serializers import (
    CpeProductSerializer,
    IdentityDecisionSerializer,
    PackageOriginSerializer,
    SoftwareIdentitySerializer,
)
from inventory.software_identity.services import (
    CPE_FAMILIES,
    LINUX_FAMILIES,
    IdentityService,
)
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

READ_ONLY = ["get", "head", "options"]


class SoftwareIdentityViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    http_method_names = READ_ONLY
    queryset = SoftwareIdentity.objects.select_related("entry")
    serializer_class = SoftwareIdentitySerializer
    model = SoftwareIdentity
    filterset_fields = ["status", "family", "product", "match_key", "reason", "entry"]
    search_fields = ["entry__name", "product", "match_key"]

    @action(detail=False, methods=["get"])
    def review(self, request):
        """
        Products to check, one row per key, on most machines first: waiting
        for an admin (status review, the default) or identified automatically
        (status matched, Windows and macOS: Linux packages have no catalog).
        """
        status = request.query_params.get("status", REVIEW)
        if status not in (REVIEW, MATCHED):
            raise ValidationError({"status": f"{REVIEW} or {MATCHED}"})
        identities = SoftwareIdentity.objects.filter(status=status)
        if status == MATCHED:
            identities = identities.filter(family__in=CPE_FAMILIES)
        groups = (
            identities.values("family", "match_key")
            .annotate(
                name=Min("entry__name"),
                entries=Count("id", distinct=True),
                # Two versions on one machine count once
                machines=Count("entry__assets", distinct=True),
            )
            .order_by("-machines", "family", "match_key")
        )
        page = self.paginate_queryset(groups)
        rows = page if page is not None else list(groups)
        for row in rows:
            top = (
                identities.filter(family=row["family"], match_key=row["match_key"])
                .order_by("-entry__installation_number", "id")
                .values("candidates", "product")
                .first()
                or {}
            )
            row["candidates"] = top.get("candidates") or []
            row["product"] = top.get("product", "")
        if page is not None:
            return self.get_paginated_response(rows)
        return Response(rows)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        state = CpeIndexState.current()
        mapped_assets = InventoryBase.objects.filter(
            template__software_mappings__isnull=False
        ).distinct()
        return Response(
            {
                "index": {
                    "version": state.version,
                    "source_date": state.source_date,
                    "synced_at": state.synced_at,
                    "product_count": state.product_count,
                },
                "counts": list(
                    SoftwareIdentity.objects.values("family", "status")
                    .annotate(count=Count("id"))
                    .order_by("family", "status")
                ),
                "pending": SoftwareDictionary.objects.filter(
                    identity__isnull=True
                ).count(),
                "machines_unknown_platform": mapped_assets.filter(
                    Q(platform__isnull=True) | Q(platform__key="")
                ).count(),
                "origins": self._origins(),
            }
        )

    @staticmethod
    def _origins():
        """
        Package origins seen on Linux entries, with the distribution they name:
        covered origins first, then third parties, then no origin, each by
        number of installed packages.
        """
        known = IdentityService.known_origins()
        entries = SoftwareDictionary.objects.filter(
            platform_family__in=LINUX_FAMILIES, package_origin__isnull=False
        ).values("package_origin")
        # Two queries: summing installations over the machines join would
        # count each entry once per machine
        machines = dict(
            entries.annotate(n=Count("assets", distinct=True)).values_list(
                "package_origin", "n"
            )
        )
        rows = [
            {
                **row,
                "machines": machines.get(row["package_origin"], 0),
                "distribution": known.get(row["package_origin"].strip().lower()),
            }
            for row in entries.annotate(
                entries=Count("id"), installations=Sum("installation_number")
            ).order_by()
        ]

        def group(row):
            if row["distribution"]:
                return 0
            return 1 if row["package_origin"] else 2

        return sorted(
            rows,
            key=lambda row: (group(row), -row["installations"], row["package_origin"]),
        )


class IdentityDecisionViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    http_method_names = ["get", "post", "delete", "head", "options"]
    queryset = IdentityDecision.objects.all()
    serializer_class = IdentityDecisionSerializer
    model = IdentityDecision
    filterset_fields = ["family", "match_key", "source", "product"]
    ordering = ["family", "match_key", "source"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        try:
            IdentityService.revert(instance)
        except ValueError as error:
            raise ValidationError(str(error))


class CpeProductViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    http_method_names = READ_ONLY
    queryset = CpeProduct.objects.all()
    serializer_class = CpeProductSerializer
    model = CpeProduct
    filterset_fields = ["vendor", "product"]
    search_fields = ["vendor", "product"]
    ordering = ["-popularity", "vendor", "product"]


class PackageOriginViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]
    queryset = PackageOrigin.objects.all()
    serializer_class = PackageOriginSerializer
    model = PackageOrigin
    filterset_fields = ["id", "name", "distribution"]
    search_fields = ["name", "distribution"]
    ordering = ["name"]

    def perform_create(self, serializer):
        origin = serializer.save()
        IdentityService.reset_origins([origin.name])

    def perform_update(self, serializer):
        previous = serializer.instance.name
        origin = serializer.save()
        IdentityService.reset_origins([previous, origin.name])

    def perform_destroy(self, instance):
        name = instance.name
        instance.delete()
        IdentityService.reset_origins([name])
