from collections import defaultdict

from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_field.models import InventoryField
from django.db.models import F, OuterRef, Q, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from ocsinventory_backend.ocs_framework import viewsets
from rest_framework import filters
from permission.permissions import DefaultModelPermissions
from rest_framework.response import Response
from virtualcolumn.models import VirtualCol


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

    def _get_virtual_cols(self, request):
        """
        Read ?virtual_cols=1,3 and return the columns the user may see

        Visibility is filtered again here, the column viewset is out of reach.
        """
        raw = request.query_params.get("virtual_cols")
        if not raw:
            return []

        ids = [int(item) for item in raw.split(",") if item.strip().isdigit()]
        if not ids:
            return []

        user = request.user
        columns = VirtualCol.objects.filter(id__in=ids, target="asset").filter(
            Q(visibility="public") | Q(user=user) | Q(groups__in=user.groups.all())
        )

        return list(columns.distinct())

    def _build_virtual_col_map(self, columns, asset_ids):
        """
        Return {asset_id: {"<column name>": value}}, one query for the page

        A Field belongs to a single Template, so filtering on every mapped id
        at once gives each asset the entry of its own template and no other.
        """
        if not columns or not asset_ids:
            return {}

        # field id -> column name, to walk the rows back
        column_by_field = {}
        for column in columns:
            for field_id in column.field_ids():
                column_by_field[field_id] = column.name

        if not column_by_field:
            return {}

        rows = InventoryField.objects.filter(
            inventory_section__base_id__in=asset_ids,
            template_field_id__in=column_by_field.keys(),
        ).values_list("inventory_section__base_id", "template_field_id", "value")

        col_map = defaultdict(dict)
        extra_values = defaultdict(int)

        for asset_id, field_id, value in rows:
            name = column_by_field[field_id]
            if name in col_map[asset_id]:
                extra_values[(asset_id, name)] += 1
                continue
            col_map[asset_id][name] = value

        for (asset_id, name), count in extra_values.items():
            col_map[asset_id][name] = f"{col_map[asset_id][name]} (+{count})"

        return col_map

    def _get_sorted_virtual_col(self, columns):
        """
        Return (column, descending) when the ordering asks for a virtual column

        The header is sent as the ordering key, so it matches no model field
        and DRF would silently drop it.
        """
        ordering = self.request.query_params.get("ordering") or ""
        descending = ordering.startswith("-")
        name = ordering[1:] if descending else ordering

        return next((column for column in columns if column.name == name), None), (
            descending
        )

    def _order_by_virtual_col(self, queryset, column, descending):
        """
        Sort on the value the column shows.

        A correlated subquery beats a join and an aggregate by an order of
        magnitude here (21 ms vs 292 ms on 20 000 assets). Ordering it by id
        keeps the sort key equal to the value the cell displays.
        """
        value = Subquery(
            InventoryField.objects.filter(
                inventory_section__base_id=OuterRef("pk"),
                template_field_id__in=column.field_ids(),
            )
            .order_by("id")
            .values("value")[:1]
        )

        ordered = queryset.annotate(virtual_col_order=value)
        order = F("virtual_col_order")

        # assets out of the mapping have no value, they go last either way
        return ordered.order_by(
            order.desc(nulls_last=True) if descending else order.asc(nulls_last=True)
        )

    def filter_queryset(self, queryset):
        """
        Let the quick search and the sort reach the displayed virtual columns

        Only the mapped fields are searched, never the whole inventory : an
        unbounded lookup would scan millions of value rows on every keystroke.
        """
        columns = self._get_virtual_cols(self.request)
        if not columns:
            return super().filter_queryset(queryset)

        term = self.request.query_params.get("search")
        sorted_column, descending = self._get_sorted_virtual_col(columns)

        field_ids = []
        if term:
            for column in columns:
                field_ids.extend(column.field_ids())

        if not field_ids and sorted_column is None:
            return super().filter_queryset(queryset)

        # the other filters apply to both sides of the search
        narrowed = DjangoFilterBackend().filter_queryset(self.request, queryset, self)

        if field_ids:
            on_base_fields = filters.SearchFilter().filter_queryset(
                self.request, narrowed, self
            )
            in_columns = narrowed.filter(
                inventory_sections__fields__template_field_id__in=field_ids,
                inventory_sections__fields__value__icontains=term,
            )
            # matching by primary key keeps the join from duplicating rows
            narrowed = queryset.filter(
                Q(pk__in=on_base_fields.values("pk"))
                | Q(pk__in=in_columns.values("pk"))
            )
        else:
            narrowed = filters.SearchFilter().filter_queryset(
                self.request, narrowed, self
            )

        if sorted_column is None:
            return filters.OrderingFilter().filter_queryset(
                self.request, narrowed, self
            )

        return self._order_by_virtual_col(narrowed, sorted_column, descending)

    def list(self, request, *args, **kwargs):
        """
        The default listing, plus the virtual columns asked for in the URL

        Values are resolved once for the page and passed by serializer context,
        so a column costs one query and not one per asset.
        """
        columns = self._get_virtual_cols(request)
        if not columns:
            return super().list(request, *args, **kwargs)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        assets = page if page is not None else list(queryset)

        context = self.get_serializer_context()
        context["virtual_col_map"] = self._build_virtual_col_map(
            columns, [asset.pk for asset in assets]
        )
        context["virtual_col_names"] = [column.name for column in columns]

        serializer = self.get_serializer_class()(assets, many=True, context=context)

        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response(serializer.data)
