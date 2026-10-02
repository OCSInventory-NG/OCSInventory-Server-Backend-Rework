from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .permissions import HasDebugMode
from .resolver import resolve_calls
from .serializers import DebugResolveSerializer


class DebugViewSet(viewsets.ViewSet):
    permission_classes = [HasDebugMode]

    @extend_schema(
        description=(
            "Resolve API calls made by a frontend page into the permissions "
            "they require, used by the frontend debug mode."
        ),
        request=DebugResolveSerializer,
    )
    @action(detail=False, methods=["post"], url_path="resolve")
    def resolve(self, request):
        serializer = DebugResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(resolve_calls(serializer.validated_data["calls"]))
