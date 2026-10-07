from inventory.software_identity.views import (
    CpeProductViewSet,
    IdentityDecisionViewSet,
    SoftwareIdentityViewSet,
)


class SoftwareIdentityRouter:
    """Register API routes for software identities"""

    @staticmethod
    def defineRoutes(defaultRouter):
        defaultRouter.register(r"software_identities", SoftwareIdentityViewSet)
        defaultRouter.register(r"software_identity_decisions", IdentityDecisionViewSet)
        defaultRouter.register(r"cpe_products", CpeProductViewSet)
        return defaultRouter
