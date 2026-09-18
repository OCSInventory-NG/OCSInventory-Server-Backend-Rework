from .views import CpeMatchViewSet, CveReportViewSet


class SecurityRouter:
    """
    Router class is intended to define the route related to an app
    defineRoutes method need to be defined and called in main urls.py
    """

    @staticmethod
    def defineRoutes(defaultRouter):
        """
        This method will provide the routes related to the app and return the new routes
        """
        defaultRouter.register(r"security/cpe-matches", CpeMatchViewSet)
        defaultRouter.register(r"security/cve-reports", CveReportViewSet)
        return defaultRouter
