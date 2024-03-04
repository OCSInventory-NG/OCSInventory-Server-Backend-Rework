from rest_framework import serializers
from search.models import Search


class SearchSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Search
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}
