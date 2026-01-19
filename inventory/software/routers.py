from inventory.software.views import SoftwareDictionaryViewSet, SoftwareMappingViewSet


class SoftwareRouter:
    """Register API routes for the software mapping"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"software_mapping", SoftwareMappingViewSet)
        defaultRouter.register(r"software_dictionary", SoftwareDictionaryViewSet)
        return defaultRouter
