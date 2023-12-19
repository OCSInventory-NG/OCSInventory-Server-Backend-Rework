from asset.inventory_section.views import InventorySectionViewSet


class InventorySectionRouter:
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
        defaultRouter.register(r"asset/sections", InventorySectionViewSet)
        return defaultRouter
