from frontend.dashboard.models import Dashboard
from rest_framework import serializers


class DashboardSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation.
    """

    class Meta:
        """
        Define the linked model and the fields registered in the API.
        """

        model = Dashboard
        fields = [
            "visibility",
            "user",
            "groups",
            "allow_group_modification",
            "name",
            "layout",
        ]
