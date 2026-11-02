from security.views import (
    ExclusionViewSet,
    ExposureViewSet,
    VulnerabilityViewSet,
)


class SecurityRouter:
    """Register API routes for vulnerabilities"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"vulnerabilities", VulnerabilityViewSet)
        defaultRouter.register(r"vulnerability_exposures", ExposureViewSet)
        defaultRouter.register(r"vulnerability_exclusions", ExclusionViewSet)
        return defaultRouter
