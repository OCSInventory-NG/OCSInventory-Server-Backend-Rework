from dashboard.layout.models import DashboardLayout
from rest_framework import serializers


class DashboardLayoutSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation.
    """

    class Meta:
        """
        Define the linked model and the fields registered in the API.
        """

        model = DashboardLayout
        fields = [
            "id",
            "visibility",
            "user",
            "groups",
            "allow_group_modification",
            "name",
            "layout",
        ]
