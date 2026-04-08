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

    def _build_condition_q(self, condition):
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]
        obj = condition["object"]
        TEXT_OPERATORS = {"icontains", "iexact", "istartswith", "iendswith"}

        if (operator in TEXT_OPERATORS and isinstance(value, int)) or value == "":
            operator = "exact"

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
            index = 0

            for condition in and_conditions:
                if masterindex > 0 and index == 0:
                    links[masterindex] = condition["link"]

                condition_q = self._build_condition_q(condition)
                condition_qs = InventoryBase.objects.filter(condition_q).distinct("pk")
                group_qs = self._combine_querysets(
                    group_qs, condition_qs, condition.get("link", "AND")
                )
                index += 1

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
            for condition in and_conditions:
                obj = condition.get("object")
                if obj not in self.RELATED_MODELS:
                    continue

                related = obj
                if related == "inventory_sections":
                    q = Q(template_section__exact=condition["section"])
                    q &= Q(fields__template_field__exact=condition["field"])
                    operator = condition["operator"]
                    value = condition["value"]
                    TEXT_OPERATORS = {"icontains", "iexact", "istartswith", "iendswith"}
                    if operator in TEXT_OPERATORS and isinstance(value, int):
                        operator = "exact"
                    q &= Q(**{f"fields__value__{operator}": value})
                else:
                    field = condition["field"]
                    operator = condition["operator"]
                    value = condition["value"]
                    TEXT_OPERATORS = {"icontains", "iexact", "istartswith", "iendswith"}
                    if operator in TEXT_OPERATORS and isinstance(value, int):
                        operator = "exact"
                    q = Q(**{f"{field}__{operator}": value})

                rel_q[related] |= q

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

        manyToMany = ["snmpscanner", "software_dictionary_entries"]

        for related, q in rel_q.items():
            model = self.RELATED_MODELS.get(related)
            if model is None:
                continue

            fk = self.RELATED_MODEL_FK.get(related)
            if related in manyToMany:
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

                values = list(qs.values())

                for row in values:
                    inv_id = row.get(f"{fk}_id")
                    if inv_id is not None:
                        if related == "inventory_sections":
                            fieldrow = {}

                            qsf = InventoryField.objects.filter(
                                inventory_section=row.get("id")
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
                            match_map[inv_id][related].append(row)

        return match_map

    def post(self, request, *args, **kwargs):
        data = request.data.get("search_data", [])
        ungroup = request.data.get("ungroup", False)

        try:
            qs = self.process_search(data)
            page = self.paginate_queryset(qs)

            rel_q = self._extract_match_filters(data)
            if page is not None:
                inventory_ids = [obj.pk for obj in page]
                match_map = self._build_match_map(inventory_ids, rel_q)
                if ungroup:
                    ungrouped_objects = []
                    for obj in page:
                        matches = match_map.get(obj.pk, {})
                        if matches:
                            for related, items in matches.items():
                                for item in items:
                                    single_match_context = {
                                        "request": request,
                                        "match_map": {obj.pk: {related: [item]}},
                                    }
                                    serializer = InventoryBaseSerializer(
                                        obj, context=single_match_context
                                    )
                                    ungrouped_objects.append(serializer.data)
                        else:
                            serializer = InventoryBaseSerializer(
                                obj, context={"request": request, "match_map": {}}
                            )
                            ungrouped_objects.append(serializer.data)

                    return self.get_paginated_response(ungrouped_objects)
                else:
                    serializer = InventoryBaseSerializer(
                        page,
                        many=True,
                        context={"request": request, "match_map": match_map},
                    )
                    return self.get_paginated_response(serializer.data)

            inventory_ids = list(qs.values_list("id", flat=True))
            match_map = self._build_match_map(inventory_ids, rel_q)

            if ungroup:
                ungrouped_objects = []
                for obj in qs:
                    matches = match_map.get(obj.pk, {})
                    if matches:
                        for related, items in matches.items():
                            for item in items:
                                single_match_context = {
                                    "request": request,
                                    "match_map": {obj.pk: {related: [item]}},
                                }
                                serializer = InventoryBaseSerializer(
                                    obj, context=single_match_context
                                )
                                ungrouped_objects.append(serializer.data)
                    else:
                        serializer = InventoryBaseSerializer(
                            obj, context={"request": request, "match_map": {}}
                        )
                        ungrouped_objects.append(serializer.data)

                return Response(ungrouped_objects, status=200)

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
