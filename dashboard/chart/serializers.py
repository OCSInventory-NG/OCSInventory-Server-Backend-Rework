from rest_framework import serializers


class DashboardChartDescriptorSerializer(serializers.Serializer):
    """
    Describes one chart available on the dashboard (returned by the list action)
    """

    category = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    charttype = serializers.CharField()


class DashboardChartCounterSerializer(serializers.Serializer):
    """
    Response shape for the *Counter* charts (total_ALL, total_WIN, ...)
    """

    total = serializers.IntegerField()
    contacted = serializers.IntegerField()


class DashboardChartTotalSerializer(serializers.Serializer):
    """
    Response shape for the simple totals (nb_netdevices, nb_networks)
    """

    total = serializers.IntegerField()


class DashboardChartSeriesSerializer(serializers.Serializer):
    """
    Response shape shared by the series-based charts
    (oscount, lastcontacted, networks)
    """

    options = serializers.JSONField()
    series = serializers.JSONField()
