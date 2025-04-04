from inventory.category.models import Category
from inventory.category.serializers import CategorySerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class CategoryViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    model = Category

    filterset_fields = ["id", "name", "description", "inventory_sections", "is_protected"]
