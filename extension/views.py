from django_filters.rest_framework import DjangoFilterBackend
from extension.models import Extension
from extension.serializers import ExtensionSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class ExtensionViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Extension.objects.all()
    serializer_class = ExtensionSerializer
    model = Extension
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        "name",
        "description",
        "version",
        "author",
        "enabled",
        "django_app",
    ]
    ordering_fields = [
        "id",
        "name",
        "description",
        "version",
        "author",
        "enabled",
        "django_app",
    ]
    filterset_fields = [
        "name",
        "description",
        "version",
        "author",
        "enabled",
        "django_app",
    ]

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="enabled",
    )
    def enabled(self, request):
        qs = Extension.objects.filter(enabled=True).values("django_app")
        return Response([x["django_app"] for x in qs])
