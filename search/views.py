from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
import logging

from asset.inventory_base.models import InventoryBase
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

        self.LOGGER.info('Start search construction query')

        return Response(
            {'message': 'Test search'},
            status=201)