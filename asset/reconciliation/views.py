import logging

from asset.inventory_base.models import InventoryBase
from asset.services import ReconciliationService
from rest_framework.response import Response
from rest_framework.views import APIView


class ReconciliationView(APIView):
    """
    Check the asset existence based on reconciliation criteria.
    This view is reachable at the /asset/reconciliation/ endpoint.

    POST:
    Check if an asset exists based on reconciliation criteria.
    Returns {"id": asset_id} if found, else {"id": False}.
    """

    permission_classes = []

    LOGGER = logging.getLogger(__name__)

    def post(self, request, *args, **kwargs):
        """
        Checks if an asset exists based on the provided data and reconciliation
        fields. Does not create or modify any data.

        args:
            request: request object
            args: args
            kwargs: kwargs

        returns:
            Response object
        """
        data = request.data

        try:
            reconciliation_filter = ReconciliationService().get_reconciliation_filter(data)
        except ValueError as e:
            self.LOGGER.warning(f"Reconciliation failed: {e}")
            return Response({"error": str(e)}, status=400)

        asset = InventoryBase.objects.filter(**reconciliation_filter).first()

        if asset:
            return Response({"id": asset.id}, status=200)
        else:
            return Response({"id": False}, status=200)