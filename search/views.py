import logging

from accountinfo.models import AccountinfoData
from asset.inventory_base.models import InventoryBase
from django.core import serializers
from django.db.models import Q
from django.http import HttpResponse
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.response import Response
from rest_framework.views import APIView
from search.models import Search
from search.serializers import SearchSerializer


class SearchView(APIView):
    """
    Manage multisearch feature
    This view is reachable at the /search/ endpoint

    POST:
    Get serach post parameters, construct the search query and
    return the result
    """

    permission_classes = []

    LOGGER = logging.getLogger(__name__)

    def process_search(self, data):
        # Initializing the Q filter list
        filters = []
        links = {}
        masterindex = 0

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
                            **{f"{obj}__fields__template_field__exact": condition["field"]}
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

            query_set = InventoryBase.objects.filter(q_object).distinct('pk')
        else:
            query_set = []

        return query_set

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
            qs_json = serializers.serialize("json", self.process_search(data))

            return HttpResponse(qs_json, content_type="application/json")
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

    def update(self, request, *args, **kwargs):
        search = self.get_object()
        user = request.user

        # check if user is the creator
        if search.user == user:
            return super().update(request, *args, **kwargs)

        # for group private searches, check if group modification is allowed
        if search.visibility == "private_group" and not search.allow_group_modification:
            return Response(
                {"detail": "You do not have permission to modify this search."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif (
            search.visibility == "private_group"
            and search.allow_group_modification
            and not search.groups.filter(id__in=user.groups.all())
        ):
            return Response(
                {"detail": "You do not have permission to modify this search."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # for public searches, check if user is the creator
        if search.visibility == "public" and search.user != user:
            return Response(
                {"detail": "You do not have permission to modify this search."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().update(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        user = request.user
        queryset = self.get_queryset()
        queryset = queryset.filter(
            Q(visibility="public") | Q(user=user) | Q(groups__in=user.groups.all())
        ).distinct()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        search = self.get_object()
        user = request.user
        if search.user == user:
            return super().destroy(request, *args, **kwargs)
        return Response(
            {"detail": "You do not have permission to delete this search."},
            status=status.HTTP_403_FORBIDDEN,
        )
