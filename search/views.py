import logging
from collections import defaultdict

from accountinfo.models import AccountinfoData
from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from asset.log.models import Log
from deployment.result.models import Result
from django.db.models import Q
from inventory.field.models import Field
from inventory.software.models import SoftwareDictionary
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from search.models import Search
from search.serializers import SearchSerializer
from snmp.scanner.models import SnmpScanner


class SearchView(GenericAPIView):
    """
    Manage multisearch feature
    This view is reachable at the /search/ endpoint

    POST:
    Get serach post parameters, construct the search query and
    return the result
    """

    permission_classes = []
    serializer_class = InventoryBaseSerializer

    LOGGER = logging.getLogger(__name__)

    RELATED_MODELS = {
        "results": Result,
        "logs": Log,
        "snmpscanner": SnmpScanner,
        "inventory_sections": InventorySection,
        "software_dictionary_entries": SoftwareDictionary,
    }

    RELATED_MODEL_FK = {
        "results": "asset",
        "logs": "asset",
        "snmpscanner": "assets",
        "inventory_sections": "base",
        "software_dictionary_entries": "assets",
    }

    SAME_ROW_RELATED_MODELS = {
        "results",
        "logs",
        "snmpscanner",
        "software_dictionary_entries",
    }
    MANY_TO_MANY_RELATED_MODELS = {
        "snmpscanner",
        "software_dictionary_entries",
    }
    UNGROUP_RELATED_ORDER = (
        "results",
        "logs",
        "snmpscanner",
        "inventory_sections",
        "software_dictionary_entries",
    )

    TEXT_OPERATORS = {"icontains", "iexact", "istartswith", "iendswith"}

    def _normalize_operator(self, operator, value):
        if (operator in self.TEXT_OPERATORS and isinstance(value, int)) or value in (
            "",
            None,
        ):
            return "exact"
        return operator

    def _build_condition_q(self, condition):
        field = condition["field"]
        value = condition["value"]
        obj = condition["object"]
        operator = self._normalize_operator(condition["operator"], value)

        # Construction of the Q condition
        if obj == "InventoryBase":
            condition_q = Q(**{f"{field}__{operator}": value})
        # Special process if accountinfo
        elif obj == "AccountinfoConfig":
            if operator == "iexact" and condition["fieldtype"] != "checkbox":
                if condition["fieldtype"] == "select":
                    matching_objects = AccountinfoData.objects.filter(
                        **{f"accountdata__{field}__value__contains": value},
                        object_slug="inventory_base.inventorybase",
                    ).values_list("object_id")
                else:
                    matching_objects = AccountinfoData.objects.filter(
                        accountdata__contains={f"{field}": value},
                        object_slug="inventory_base.inventorybase",
                    ).values_list("object_id")
                if matching_objects:
                    condition_q = Q(id__in=matching_objects)
                else:
                    id_to_exclude = InventoryBase.objects.all().values_list("id")
                    condition_q = ~Q(id__in=id_to_exclude)
            else:
                matching_objects = AccountinfoData.objects.filter(
                    accountdata__has_key=f"{field}",
                    object_slug="inventory_base.inventorybase",
                )
                if matching_objects:
                    result = []
                    for matching_object in matching_objects:
                        for key, data in matching_object.accountdata.items():
                            if int(key) == int(field):
                                if (
                                    operator == "icontains"
                                    and data is not None
                                    and value.lower() in data.lower()
                                ):
                                    result.append(matching_object.object_id)
                                elif (
                                    operator == "istartswith"
                                    and data is not None
                                    and data.lower().startswith(value.lower())
                                ):
                                    result.append(matching_object.object_id)
                                elif (
                                    operator == "iendswith"
                                    and data is not None
                                    and data.lower().endswith(value.lower())
                                ):
                                    result.append(matching_object.object_id)
                                elif (
                                    operator == "iexact"
                                    and condition["fieldtype"] == "checkbox"
                                    and int(value) in data
                                ):
                                    result.append(matching_object.object_id)
                    if len(result) > 0:
                        condition_q = Q(id__in=result)
                    else:
                        id_to_exclude = InventoryBase.objects.all().values_list("id")
                        condition_q = ~Q(id__in=id_to_exclude)
                else:
                    id_to_exclude = InventoryBase.objects.all().values_list("id")
                    condition_q = ~Q(id__in=id_to_exclude)
        # Foreign key process
        else:
            if obj == "inventory_sections":
                condition_q = Q(
                    **{f"{obj}__template_section__exact": condition["section"]}
                )
                condition_q &= Q(
                    **{f"{obj}__fields__template_field__exact": condition["field"]}
                )
                condition_q &= Q(**{f"{obj}__fields__value__{operator}": value})
            else:
                condition_q = Q(**{f"{obj}__{field}__{operator}": value})

        return condition_q

    def _build_related_condition_q(self, condition):
        field = condition["field"]
        operator = self._normalize_operator(condition["operator"], condition["value"])

        if condition["object"] == "inventory_sections":
            q = Q(template_section__exact=condition["section"])
            q &= Q(fields__template_field__exact=condition["field"])
            q &= Q(**{f"fields__value__{operator}": condition["value"]})
            return q

        return Q(**{f"{field}__{operator}": condition["value"]})

    def _build_condition_units(self, conditions, q_builder):
        """
        Group AND conditions that must target the same related row.

        Example:
        - software.name=apache2 AND software.name=apt => two units, two rows
        - software.name=adduser AND software.version=3.118 => one unit, same row
        """
        units = []
        pending = None

        for condition in conditions:
            q = q_builder(condition)
            obj = condition["object"]
            field = condition["field"]
            link = condition.get("link", "AND")

            can_merge = (
                pending is not None
                and link == "AND"
                and obj in self.SAME_ROW_RELATED_MODELS
                and pending["object"] == obj
                and field not in pending["fields"]
            )

            if can_merge:
                pending["q"] &= q
                pending["fields"].add(field)
                continue

            if pending is not None:
                units.append(pending)

            pending = {
                "link": link,
                "object": obj,
                "fields": {field},
                "q": q,
            }

        if pending is not None:
            units.append(pending)

        return units

    def _combine_querysets(self, base_qs, condition_qs, link):
        if base_qs is None:
            return condition_qs
        if link == "OR":
            return base_qs | condition_qs
        return base_qs.filter(pk__in=condition_qs.values("pk"))

    def process_search(self, data):
        filters = []
        links = {}
        masterindex = 0

        for and_conditions in data:
            group_qs = None

            if masterindex > 0 and len(and_conditions) > 0:
                links[masterindex] = and_conditions[0]["link"]

            for unit in self._build_condition_units(
                and_conditions, self._build_condition_q
            ):
                condition_q = unit["q"]
                condition_qs = InventoryBase.objects.filter(condition_q).distinct("pk")
                group_qs = self._combine_querysets(
                    group_qs, condition_qs, unit.get("link", "AND")
                )

            if group_qs is not None:
                filters.append(group_qs)
            masterindex += 1

        if len(filters) > 0:
            query_set = filters[0]
            linkindex = 1
            for qs_filter in filters[1:]:
                if links[linkindex] == "OR":
                    query_set = query_set | qs_filter
                else:
                    query_set = query_set.filter(pk__in=qs_filter.values("pk"))
                linkindex += 1
            return query_set.distinct("pk")

        return InventoryBase.objects.none()

    def _extract_match_filters(self, payload):
        """
        Returns a dict {related_name: Q()} used to fetch the related
        rows that matched at least one searched condition.
        """
        rel_q = defaultdict(Q)

        for and_conditions in payload:
            related_conditions = [
                condition
                for condition in and_conditions
                if condition.get("object") in self.RELATED_MODELS
            ]

            for unit in self._build_condition_units(
                related_conditions, self._build_related_condition_q
            ):
                related = unit["object"]
                if related not in self.RELATED_MODELS:
                    continue

                rel_q[related] |= unit["q"]

        return rel_q

    def _build_match_map(self, inventory_ids, rel_q):
        """
        Returns {inventory_id: {"results":[...], "logs":[...], ...}}
        by making one query per relation (no N+1).
        """
        match_map = defaultdict(
            lambda: {
                "results": [],
                "logs": [],
                "snmpscanner": [],
                "inventory_sections": [],
                "software_dictionary_entries": [],
            }
        )
        seen_matches = defaultdict(lambda: defaultdict(set))

        for related, q in rel_q.items():
            model = self.RELATED_MODELS.get(related)
            if model is None:
                continue

            fk = self.RELATED_MODEL_FK.get(related)
            if related in self.MANY_TO_MANY_RELATED_MODELS:
                qs = (
                    model.objects.filter(
                        **{f"{fk}__in": inventory_ids},
                    )
                    .filter(q)
                    .distinct()
                )

                for obj in qs:
                    related_ids = getattr(obj, fk).values_list("id", flat=True)
                    related_ids = [rid for rid in related_ids if rid in inventory_ids]

                    row = {
                        field.name: getattr(obj, field.name)
                        for field in model._meta.fields
                    }

                    for inv_id in related_ids:
                        row_id = row.get("id")
                        if (
                            row_id is not None
                            and row_id in seen_matches[inv_id][related]
                        ):
                            continue
                        if row_id is not None:
                            seen_matches[inv_id][related].add(row_id)
                        match_map[inv_id][related].append(row)
            else:
                qs = model.objects.filter(
                    **{f"{fk}_id__in": inventory_ids},
                ).filter(q)

                if related == "inventory_sections":
                    qs = qs.select_related("template_section")

                    for section in qs:
                        inv_id = getattr(section, f"{fk}_id", None)
                        if inv_id is None:
                            continue

                        fieldrow = {
                            "section": (
                                section.template_section.name
                                if section.template_section
                                else None
                            )
                        }

                        qsf = InventoryField.objects.filter(
                            inventory_section=section.id
                        )
                        fvalues = list(qsf.values("template_field_id", "value"))

                        field_ids = [f["template_field_id"] for f in fvalues]
                        fields = Field.objects.in_bulk(field_ids)

                        for frow in fvalues:
                            field = fields.get(frow["template_field_id"])
                            if not field:
                                continue

                            fieldrow[field.name] = frow.get("value")
                        match_map[inv_id][related].append(fieldrow)
                else:
                    values = list(qs.values())

                    for row in values:
                        inv_id = row.get(f"{fk}_id")
                        if inv_id is not None:
                            match_map[inv_id][related].append(row)

        return match_map

    def _serialize_ungrouped_row(self, obj, request, related=None, item=None):
        match_map = {}
        if related is not None and item is not None:
            match_map = {obj.pk: {related: [item]}}

        serializer = InventoryBaseSerializer(
            obj,
            context={"request": request, "match_map": match_map},
        )
        return serializer.data

    def _iter_ungrouped_match_rows(self, matches):
        for related in self.UNGROUP_RELATED_ORDER:
            for item in matches.get(related, []):
                yield related, item

    def _count_ungrouped_rows_for_asset(self, matches):
        count = sum(len(matches.get(related, [])) for related in self.UNGROUP_RELATED_ORDER)
        return count or 1

    def _build_related_rows_queryset(self, related, inventory_qs, q):
        model = self.RELATED_MODELS.get(related)
        fk = self.RELATED_MODEL_FK.get(related)

        if related in self.MANY_TO_MANY_RELATED_MODELS:
            queryset = model.objects.filter(
                **{f"{fk}__in": inventory_qs.values("pk")}
            ).filter(q)
            return queryset, f"{fk}__id"

        queryset = model.objects.filter(
            **{f"{fk}_id__in": inventory_qs.values("pk")}
        ).filter(q)
        return queryset, f"{fk}_id"

    def _count_ungrouped_rows(self, inventory_qs, rel_q):
        if not rel_q:
            return inventory_qs.count()

        total_count = 0
        base_only_qs = inventory_qs

        for related, q in rel_q.items():
            related_qs, inventory_id_field = self._build_related_rows_queryset(
                related, inventory_qs, q
            )

            if related in self.MANY_TO_MANY_RELATED_MODELS:
                total_count += related_qs.values(inventory_id_field, "id").distinct().count()
            else:
                total_count += related_qs.count()

            base_only_qs = base_only_qs.exclude(
                pk__in=related_qs.values(inventory_id_field).distinct()
            )

        return total_count + base_only_qs.count()

    def _chunked(self, iterable, size):
        chunk = []
        for item in iterable:
            chunk.append(item)
            if len(chunk) == size:
                yield chunk
                chunk = []

        if chunk:
            yield chunk

    def _get_ungrouped_page(self, inventory_qs, rel_q, request, offset, limit):
        if limit == 0:
            return []

        if not rel_q:
            page = list(inventory_qs[offset : offset + limit])
            return [self._serialize_ungrouped_row(obj, request) for obj in page]

        rows = []
        remaining_offset = offset
        remaining_limit = limit

        inventory_ids = inventory_qs.values_list("pk", flat=True).iterator(chunk_size=100)

        for chunk_ids in self._chunked(inventory_ids, 100):
            objects = InventoryBase.objects.in_bulk(chunk_ids)
            match_map = self._build_match_map(chunk_ids, rel_q)

            for inventory_id in chunk_ids:
                obj = objects.get(inventory_id)
                if obj is None:
                    continue

                matches = match_map.get(inventory_id, {})
                asset_row_count = self._count_ungrouped_rows_for_asset(matches)

                if remaining_offset >= asset_row_count:
                    remaining_offset -= asset_row_count
                    continue

                if matches:
                    rows_to_skip = remaining_offset
                    remaining_offset = 0

                    for related, item in self._iter_ungrouped_match_rows(matches):
                        if rows_to_skip:
                            rows_to_skip -= 1
                            continue

                        rows.append(
                            self._serialize_ungrouped_row(
                                obj, request, related=related, item=item
                            )
                        )
                        remaining_limit -= 1

                        if remaining_limit == 0:
                            return rows
                else:
                    if remaining_offset:
                        remaining_offset -= 1
                        continue

                    rows.append(self._serialize_ungrouped_row(obj, request))
                    remaining_limit -= 1

                    if remaining_limit == 0:
                        return rows

        return rows

    def _get_all_ungrouped_rows(self, inventory_qs, rel_q, request):
        inventory_ids = list(inventory_qs.values_list("id", flat=True))
        match_map = self._build_match_map(inventory_ids, rel_q)
        rows = []

        for obj in inventory_qs:
            matches = match_map.get(obj.pk, {})
            if matches:
                for related, item in self._iter_ungrouped_match_rows(matches):
                    rows.append(
                        self._serialize_ungrouped_row(
                            obj, request, related=related, item=item
                        )
                    )
            else:
                rows.append(self._serialize_ungrouped_row(obj, request))

        return rows

    def post(self, request, *args, **kwargs):
        data = request.data.get("search_data", [])
        ungroup = request.data.get("ungroup", False)

        try:
            qs = self.process_search(data)
            rel_q = self._extract_match_filters(data)

            if ungroup:
                paginator = self.paginator
                if paginator is not None:
                    limit = paginator.get_limit(request)
                    if limit is not None:
                        paginator.limit = limit
                        paginator.offset = paginator.get_offset(request)
                        paginator.count = self._count_ungrouped_rows(qs, rel_q)
                        paginator.request = request

                        if paginator.count > paginator.limit and paginator.template is not None:
                            paginator.display_page_controls = True

                        paginated_rows = self._get_ungrouped_page(
                            qs,
                            rel_q,
                            request,
                            paginator.offset,
                            paginator.limit,
                        )
                        return paginator.get_paginated_response(paginated_rows)

                return Response(self._get_all_ungrouped_rows(qs, rel_q, request), status=200)

            page = self.paginate_queryset(qs)
            if page is not None:
                inventory_ids = [obj.pk for obj in page]
                match_map = self._build_match_map(inventory_ids, rel_q)
                serializer = InventoryBaseSerializer(
                    page,
                    many=True,
                    context={"request": request, "match_map": match_map},
                )
                return self.get_paginated_response(serializer.data)

            inventory_ids = list(qs.values_list("id", flat=True))
            match_map = self._build_match_map(inventory_ids, rel_q)

            serializer = InventoryBaseSerializer(
                qs,
                many=True,
                context={"request": request, "match_map": match_map},
            )
            return Response(serializer.data, status=200)
        # we return a 500 an error occured
        except Exception as e:
            self.LOGGER.error(f"Error search processing: {e}")
            return Response({"error": f"Error search processing: {e}"}, status=500)


class SearchViewSet(viewsets.RestrictVisibilityViewSet):
    """
    This class will define the view behavior

    Inherits from RestrictVisibilityViewSet to restrict the visibility of the
    Search objects based on user and group membership

    Args:
        viewsets ([OCSVIewSet])
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Search.objects.all()
    serializer_class = SearchSerializer
    model = Search

    filterset_fields = [
        "id",
        "last_updated",
        "name",
        "description",
    ]
