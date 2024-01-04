import logging

from asset.inventory_base.models import InventoryBase
from django.core import serializers
from django.db.models import Q
from django.http import HttpResponse
from rest_framework.views import APIView


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

    def post(self, request, *args, **kwargs):
        """
        args:
            request: request object
            args: args
            kwargs: kwargs

        returns:
            Response object
        """

        self.LOGGER.info("Start search construction query")

        data = request.data

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

                if masterindex > 0 and index == 0:
                    links[masterindex] = condition["link"]

                # Construction of the Q condition
                condition_q = Q(**{f"{field}__{operator}": value})

                # If the previous filter was linked by "OR", use OR,
                # otherwise use AND
                if condition["link"] == "OR":
                    and_filter |= condition_q
                else:
                    and_filter &= condition_q
                
                index = index + 1

            # Adding the "AND" filter to the filter list
            filters.append(and_filter)
            masterindex = masterindex + 1

        # Construction of the final filter using AND between "OR" filters
        q_object = filters[0]
        linkindex = 1
        for q_filter in filters[1:]:
            if links[linkindex] == "OR":
                q_object |= q_filter
            else:
                q_object &= q_filter

        query_set = InventoryBase.objects.filter(q_object)
        qs_json = serializers.serialize("json", query_set)

        return HttpResponse(qs_json, content_type="application/json")
