from dashboard.chart.models import DashboardChart
from rest_framework import serializers


class DashboardChartSerializer(serializers.ModelSerializer):
    """
    This serializer class provides the API representation.
    """

    class Meta:
        """
        Define the linked model and the fields registered in the API.
        """

        model = DashboardChart
        fields = [
            "name",
            "chart_type",
        ]
