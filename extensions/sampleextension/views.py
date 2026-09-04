# Example: a REST API (list, create, update, delete).

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from permission.permissions import DefaultModelPermissions

from .models import SampleComment
from .serializer import SampleCommentSerializer


class SampleCommentViewSet(viewsets.ModelViewSet):
    permission_classes = [DefaultModelPermissions]
    serializer_class = SampleCommentSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["message", "asset__name"]
    ordering_fields = ["id", "created_at"]

    def get_queryset(self):
        # ?asset=<id> lets the frontend ask for one asset's comments only.
        queryset = SampleComment.objects.select_related("asset").all()
        asset_id = self.request.query_params.get("asset")
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)
        return queryset

    # Example: a custom endpoint next to plain CRUD.
    # GET /sampleextension/comments/count/
    @action(detail=False, methods=["get"])
    def count(self, request):
        return Response({"count": self.get_queryset().count()})
