from security.views import VulnerabilityViewSet


class SecurityRouter:
    """Register API routes for vulnerabilities"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"vulnerabilities", VulnerabilityViewSet)
        return defaultRouter
