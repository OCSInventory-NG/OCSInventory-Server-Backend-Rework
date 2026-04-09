from config.views import ConfigViewSet
from config.views import ServerInfoViewSet


class ConfigRouter:
    """
    Router class is intended to define the route related to an app
    defineRoutes method need to be defined and called in main urls.py
    """

    @staticmethod
    def defineRoutes(defaultRouter):
        """
        This method will provide the routes related to the app and return the new routes

        Args:
            defaultRouter ([DefaultRouter]): Default router from main urls.py

        Returns:
            [DefaultRouter]: Updated router with app's dedicated routes
        """
        defaultRouter.register(r"config", ConfigViewSet)
        defaultRouter.register(
            r"server-info", ServerInfoViewSet, basename="server_info"
        )
        return defaultRouter
