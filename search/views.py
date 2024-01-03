from asset.inventory_base.models import InventoryBase
from django.db.models import Q
from django.core import serializers
from django.http import HttpResponse
import logging
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

        # storing errors
        #errors = []

        data = request.data

        #try:
        # initialize empty arguments
        kwargs = {}

        for params in data:
            for param in params:
                kwargs = {
                    '{0}__{1}'.format(param['field'], param['operator']): param['value']
                }

        q_objects = Q()
        for key, value in kwargs.items():
            q_objects.add(Q(**{key: value}), Q.AND)
        
        query_set = InventoryBase.objects.filter(q_objects)
        qs_json = serializers.serialize('json', query_set)
        
        #except:
        #    errors.append('Error append in search construction')

        return HttpResponse(qs_json, content_type='application/json')