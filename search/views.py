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

    def process_search(self, data):
        # Initializing the Q filter list
        filters = []
        links = {}
        masterindex = 0
        TEXT_OPERATORS = {"icontains", "iexact", "istartswith", "iendswith"}

        # Iterating over JSON structure
        for and_conditions in data:
            and_filter = Q()
            index = 0

            # Iteration on “AND” conditions
            for condition in and_conditions:
                field = condition["field"]
                operator = condition["operator"]
                value = condition["value"]
                obj = condition["object"]
                skip = False

                if masterindex > 0 and index == 0:
                    links[masterindex] = condition["link"]

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
                            id_to_exclude = InventoryBase.objects.all().values_list(
                                "id"
                            )
                            condition_q = ~Q(id__in=id_to_exclude)
                    else:
                        matching_objects = AccountinfoData.objects.filter(
                            accountdata__has_key=f"{field}",
                            object_slug="inventory_base.inventorybase",
                        )
                        if matching_objects:
                            result = []
                            for matching_object in matching_objects:
                                for (
                                    key,
                                    data,
                                ) in matching_object.accountdata.items():
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
                                id_to_exclude = InventoryBase.objects.all().values_list(
                                    "id"
                                )
                                condition_q = ~Q(id__in=id_to_exclude)
                        else:
                            id_to_exclude = InventoryBase.objects.all().values_list(
                                "id"
                            )
                            condition_q = ~Q(id__in=id_to_exclude)
                # Foreign key process
                else:
                    if obj == "inventory_sections":
                        condition_q = Q(
                            **{f"{obj}__template_section__exact": condition["section"]}
                        )
                        condition_q &= Q(
                            **{
                                f"{obj}__fields__template_field__exact": condition[
                                    "field"
                                ]
                            }
                        )
                        condition_q &= Q(**{f"{obj}__fields__value__{operator}": value})
                    else:
                        condition_q = Q(**{f"{obj}__{field}__{operator}": value})

                # If the previous filter was linked by "OR", use OR,
                # otherwise use AND
                if skip is False:
                    if condition["link"] == "OR":
                        and_filter |= condition_q
                    else:
                        and_filter &= condition_q

                index = index + 1

            # Adding the "AND" filter to the filter list
            if len(and_filter) > 0:
                filters.append(and_filter)
            masterindex = masterindex + 1

        # Construction of the final filter using AND between "OR" filters
        if len(filters) > 0:
            q_object = filters[0]
            linkindex = 1
            for q_filter in filters[1:]:
                if links[linkindex] == "OR":
                    q_object |= q_filter
                else:
                    q_object &= q_filter

            query_set = InventoryBase.objects.filter(q_object).distinct("pk")
        else:
            query_set = InventoryBase.objects.none()

        return query_set

    def _extract_match_filters(self, payload):
        """
        Returns a dict {related_name: Q()} which represents
        the "local" filters by relation (including all conditions of this type OR/AND).
        """
        rel_q = defaultdict(Q)

        for and_conditions in payload:
            local_per_rel = defaultdict(Q)

            first_for_rel = defaultdict(lambda: True)

            for condition in and_conditions:
                obj = condition.get("object")
                if obj not in self.RELATED_MODELS:
                    continue

                related = obj
                field = condition["field"]
                operator = condition["operator"]
                value = condition["value"]
                link = condition.get("link", "AND")

                TEXT_OPERATORS = {"icontains", "iexact", "istartswith", "iendswith"}
                if operator in TEXT_OPERATORS and isinstance(value, int):
                    operator = "exact"

                if related == "inventory_sections":
                    q = Q(template_section__exact=condition["section"])
                    q &= Q(fields__template_field__exact=condition["field"])
                    q &= Q(**{f"fields__value__{operator}": value})
                else:
                    q = Q(**{f"{field}__{operator}": value})

                if first_for_rel[related]:
                    local_per_rel[related] = q
                    first_for_rel[related] = False
                else:
                    if link == "OR":
                        local_per_rel[related] |= q
                    else:
                        local_per_rel[related] &= q

            for related, q in local_per_rel.items():
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

        manyToMany = ["snmpscanner", "software_dictionary_entries"]

        for related, q in rel_q.items():
            model = self.RELATED_MODELS.get(related)
            if model is None:
                continue

            fk = self.RELATED_MODEL_FK.get(related)
            if related in manyToMany:
                qs = model.objects.filter(
                    **{f"{fk}__in": inventory_ids},
                ).filter(q)

                for obj in qs:
                    related_ids = getattr(obj, fk).values_list("id", flat=True)
                    related_ids = [rid for rid in related_ids if rid in inventory_ids]

                    row = {
                        field.name: getattr(obj, field.name)
                        for field in model._meta.fields
                    }

                    for inv_id in related_ids:
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
        """
        args:
            request: request object
            args: args
            kwargs: kwargs

        returns:
            Response object
        """

        data = request.data

        try:
            qs = self.process_search(data)
            page = self.paginate_queryset(qs)

            rel_q = self._extract_match_filters(data)
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
        except Exception as e:
            # we return a 500 an error occured
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
