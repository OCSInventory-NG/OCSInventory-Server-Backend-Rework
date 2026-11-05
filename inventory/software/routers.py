from inventory.software.views import (
    DistroReleaseViewSet,
    SoftwareDictionaryViewSet,
    SoftwareMappingViewSet,
)


class SoftwareRouter:
    """Register API routes for the software mapping"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"software_mapping", SoftwareMappingViewSet)
        defaultRouter.register(r"software_dictionary", SoftwareDictionaryViewSet)
        defaultRouter.register(r"distro_releases", DistroReleaseViewSet)
        return defaultRouter
