from accountinfo.services import AccountinfoSearch
from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import filters


class InventoryBaseViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = InventoryBase.objects.all()
    serializer_class = InventoryBaseSerializer
    model = InventoryBase
    search_fields = [
        "name",
        "description",
        "serial",
        "osname",
        "osversion",
        "uuid",
        "srcip",
        "srcmac",
        "domain",
        "agent",
        "last_update",
    ]
    ordering_fields = [
        "id",
        "name",
        "description",
        "serial",
        "osname",
        "osversion",
        "uuid",
        "srcip",
        "srcmac",
        "domain",
        "agent",
        "last_update",
    ]

    def filter_queryset(self, queryset):
        """
        Let the quick search reach the administrative data on display

        Those columns are shown whenever the listing is asked for them, but
        search_fields cannot express them : the values live in a JSON blob on a
        generic relation, not on the asset.
        """
        term = self.request.query_params.get("search")
        accountinfo = self.request.query_params.get("accountinfo")

        if not term or not (accountinfo and accountinfo.lower() == "true"):
            return super().filter_queryset(queryset)

        matched = AccountinfoSearch(
            "inventory_base.inventorybase", "ASSET"
        ).matching_object_ids(term)

        if not matched:
            return super().filter_queryset(queryset)

        # the other filters apply to both sides of the search
        narrowed = DjangoFilterBackend().filter_queryset(self.request, queryset, self)
        on_base_fields = filters.SearchFilter().filter_queryset(
            self.request, narrowed, self
        )
        combined = queryset.filter(
            Q(pk__in=on_base_fields.values("pk")) | Q(pk__in=matched)
        )

        return filters.OrderingFilter().filter_queryset(self.request, combined, self)
