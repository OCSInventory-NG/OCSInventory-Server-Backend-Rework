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
        fields = [
            "id",
            "search",
            "last_updated",
            "visibility",
            "name",
            "description",
            "allow_group_modification",
            "user",
            "groups",
        ]
        extra_kwargs = {"last_updated": {"read_only": True}}
