from inventory.software.views import SoftwareFieldMappingViewSet


class SoftwareRouter:
    """Register API routes for the software mapping"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"software_field_mappings", SoftwareFieldMappingViewSet)
        return defaultRouter
