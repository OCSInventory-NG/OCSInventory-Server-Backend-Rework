from inventory.software_identity.views import (
    CpeProductViewSet,
    IdentityDecisionViewSet,
    PackageOriginViewSet,
    SoftwareIdentityViewSet,
)


class SoftwareIdentityRouter:
    """Register API routes for software identities"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"software_identities", SoftwareIdentityViewSet)
        defaultRouter.register(r"software_identity_decisions", IdentityDecisionViewSet)
        defaultRouter.register(r"cpe_products", CpeProductViewSet)
        defaultRouter.register(r"package_origins", PackageOriginViewSet)
        return defaultRouter
