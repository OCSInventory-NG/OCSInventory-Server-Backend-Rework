from asset.inventory_base.models import InventoryBase
from asset.inventory_base.scope import visible_asset_ids_for
from django import forms
from django.db.models import Count, Prefetch, Q
from django_filters import rest_framework as filters
from inventory.software.models import SoftwareDictionary, SoftwareMapping
from inventory.software.serializers import (
    SoftwareDictionarySerializer,
    SoftwareMappingSerializer,
)
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions

VISIBLE_COUNT = "visible_installation_number"


class SoftwareMappingViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]

    queryset = SoftwareMapping.objects.all()
    serializer_class = SoftwareMappingSerializer
    model = SoftwareMapping

    filterset_fields = [
        "id",
        "template",
        "section",
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
    ]


class IntegerFilter(filters.NumberFilter):
    field_class = forms.IntegerField


class SoftwareDictionaryFilterSet(filters.FilterSet):
    installation_number = IntegerFilter(method="filter_installation_number")

    class Meta:
        model = SoftwareDictionary
        fields = [
            "id",
            "name",
            "publisher",
            "version",
            "major_version",
            "minor_version",
            "patch_version",
        ]

    def filter_installation_number(self, queryset, name, value):
        field = "installation_number"
        if VISIBLE_COUNT in queryset.query.annotations:
            field = VISIBLE_COUNT
        return queryset.filter(**{field: value})


class SoftwareDictionaryViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]

    queryset = SoftwareDictionary.objects.all()
    serializer_class = SoftwareDictionarySerializer
    model = SoftwareDictionary
    search_fields = [
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
    ]
    ordering_fields = [
        "id",
        "name",
        "publisher",
        "version",
        "major_version",
        "minor_version",
        "patch_version",
        "installation_number",
    ]
    filterset_class = SoftwareDictionaryFilterSet

    def get_queryset(self):
        queryset = super().get_queryset()
        ids = visible_asset_ids_for(self.request)
        if ids is None:
            return queryset
        return (
            queryset.annotate(
                **{
                    VISIBLE_COUNT: Count(
                        "assets", filter=Q(assets__in=ids), distinct=True
                    )
                }
            )
            .filter(**{f"{VISIBLE_COUNT}__gt": 0})
            .prefetch_related(
                Prefetch("assets", queryset=InventoryBase.objects.filter(pk__in=ids))
            )
        )

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        ordering = self.request.query_params.get("ordering")
        if VISIBLE_COUNT in queryset.query.annotations and ordering in (
            "installation_number",
            "-installation_number",
        ):
            direction = "-" if ordering.startswith("-") else ""
            queryset = queryset.order_by(f"{direction}{VISIBLE_COUNT}", "id")
        return queryset
