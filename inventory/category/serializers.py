from inventory.category.models import Category
from rest_framework import serializers


class CategorySerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Category
        fields = ["id", "name", "description", "sections"]
