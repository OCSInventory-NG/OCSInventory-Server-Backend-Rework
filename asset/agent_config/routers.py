from asset.agent_config.views import AgentConfigViewSet


class AgentConfigRouter:
    """
    Router class is intended to define the route related to an app
    defineRoutes method need to be defined and called in main urls.py
    """

    @staticmethod
    def defineRoutes(defaultRouter):
        """
        Define app's routes

        Args:
            defaultRouter ([DefaultRouter]): Default router from main urls.py

        Returns:
            [DefaultRouter]: Updated router with app's dedicated routes
        """
        defaultRouter.register(
            r"asset/configs", AgentConfigViewSet, basename="asset_agent_config"
        )
        return defaultRouter
