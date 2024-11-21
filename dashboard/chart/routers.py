from dashboard.chart.views import DashboardChartViewSet


class DashboardChartRouter:
    """
    Router class is intended to define the route related to an app
    defineRoutes method need to be defined and called in main urls.py
    """

    @staticmethod
    def defineRoutes(defaultRouter):
        """
        This method will provide the routes related to the app
        and return the new routes.
        """

        defaultRouter.register(r"dashboard/chart", DashboardChartViewSet, basename="dashboard-chart")
        return defaultRouter
