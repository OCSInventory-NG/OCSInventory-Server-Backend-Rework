from .views import (
    AssetEOLStatusViewSet,
    ComplianceResultViewSet,
    ComplianceRuleViewSet,
    ComplianceTargetViewSet,
    WindowsBuildMappingViewSet,
)


class ComplianceRouter:
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
        defaultRouter.register(r"compliance/rules", ComplianceRuleViewSet)
        defaultRouter.register(r"compliance/targets", ComplianceTargetViewSet)
        defaultRouter.register(r"compliance/results", ComplianceResultViewSet)
        defaultRouter.register(r"compliance/eol-status", AssetEOLStatusViewSet)
        defaultRouter.register(
            r"compliance/windows-build-mapping", WindowsBuildMappingViewSet
        )
        return defaultRouter
