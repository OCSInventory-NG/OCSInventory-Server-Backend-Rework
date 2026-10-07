from asset.inventory_base.models import InventoryBase
from django.db.models import Count, Min, Q, Sum
from inventory.software.models import SoftwareDictionary
from inventory.software_identity.models import (
    CpeIndexState,
    CpeProduct,
    IdentityDecision,
    SoftwareIdentity,
)
from inventory.software_identity.normalizers.base import REVIEW
from inventory.software_identity.serializers import (
    CpeProductSerializer,
    IdentityDecisionSerializer,
    SoftwareIdentitySerializer,
)
from inventory.software_identity.services import IdentityService
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
        """Products waiting for an admin, one row per key, most installed first."""
        groups = (
            SoftwareIdentity.objects.filter(status=REVIEW)
            .values("family", "match_key")
            .annotate(
                name=Min("entry__name"),
                entries=Count("id"),
                machines=Sum("entry__installation_number"),
            )
            .order_by("-machines", "family", "match_key")
        )
        page = self.paginate_queryset(groups)
        rows = page if page is not None else list(groups)
        for row in rows:
            row["candidates"] = (
                SoftwareIdentity.objects.filter(
                    status=REVIEW, family=row["family"], match_key=row["match_key"]
                )
                .order_by("-entry__installation_number", "id")
                .values_list("candidates", flat=True)
                .first()
                or []
            )
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
            }
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
