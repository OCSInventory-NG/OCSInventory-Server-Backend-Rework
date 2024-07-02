from django.db import models


class DashboardChart(models.Model):
    """
    Chart model for dashboard

    Fields:
    - name: chart name
    - chart_type: chart type
    - data: JSON data for the chart
    """

    CHART_TYPES = [
        ("line", "Line"),
        ("bar", "Bar"),
        ("donut", "Donut"),
        ('counter', 'Counter'),
    ]

    name = models.CharField(max_length=100)
    chart_type = models.CharField(max_length=100)
