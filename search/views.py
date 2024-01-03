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

        # Initialisation de la liste des filtres Q
        filters = []

        # Itération sur la structure JSON
        for and_conditions in data:
            and_filter = Q()

            # Itération sur les conditions "ET"
            for condition in and_conditions:
                field = condition["field"]
                operator = condition["operator"]
                value = condition["value"]

                # Construction de la condition Q
                condition_q = Q(**{f"{field}__{operator}": value})

                # Si le filtre précédent était lié par "OR", utilisez OR,
                # sinon utilisez AND
                if condition["link"] == "OR":
                    and_filter |= condition_q
                else:
                    and_filter &= condition_q

            # Ajout du filtre "ET" à la liste des filtres
            filters.append(and_filter)

        # Construction du filtre final en utilisant ET entre les filtres "OR"
        q_object = filters[0]
        for q_filter in filters[1:]:
            q_object &= q_filter

        query_set = InventoryBase.objects.filter(q_object)
        qs_json = serializers.serialize("json", query_set)

        return HttpResponse(qs_json, content_type="application/json")
