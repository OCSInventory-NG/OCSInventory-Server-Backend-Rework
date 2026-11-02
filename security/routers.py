from security.views import (
    ExclusionViewSet,
    ExposureViewSet,
    SecuritySettingsViewSet,
    VulnerabilityViewSet,
)


class SecurityRouter:
    """Register API routes for vulnerabilities"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"vulnerabilities", VulnerabilityViewSet)
        defaultRouter.register(r"vulnerability_exposures", ExposureViewSet)
        defaultRouter.register(r"vulnerability_exclusions", ExclusionViewSet)
        defaultRouter.register(r"security_settings", SecuritySettingsViewSet)
        return defaultRouter
