from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from auth.auth_config.models import AuthConfig
from auth.auth_mapping.models import AuthMapping
from django.conf import settings
import logging
from django.contrib.auth import get_user_model


class CustomOIDCBackend(OIDCAuthenticationBackend):

    logger = logging.getLogger(__name__)

    def __init__(self):

        self.configs = AuthConfig.objects.filter(auth_method__name="OIDC",
                                                 enabled=True).order_by("priority")
        self.mappings = AuthMapping.objects.filter(
                                                   auth_config__auth_method__name="OIDC")
        # TODO : get the first enabled config for now but figure out how to handle multiple configs (or prevent it)
        oidc_config = self.configs[0]

        self.OIDC_OP_TOKEN_ENDPOINT = oidc_config.config["TOKEN_ENDPOINT"]
        self.OIDC_OP_USER_ENDPOINT = oidc_config.config["USERINFO_ENDPOINT"]
        self.OIDC_OP_JWKS_ENDPOINT = oidc_config.config["JWKS_ENDPOINT"]
        self.OIDC_RP_CLIENT_ID = oidc_config.config["CLIENT_ID"]
        self.OIDC_RP_CLIENT_SECRET = oidc_config.config["CLIENT_SECRET"]
        self.OIDC_RP_SIGN_ALGO = oidc_config.config["SIGN_ALGO"]
        self.OIDC_RP_IDP_SIGN_KEY = None
        settings.OIDC_AUTHENTICATION_CALLBACK_URL = "callback"

        if self.OIDC_RP_SIGN_ALGO.startswith("RS") and (
            self.OIDC_RP_IDP_SIGN_KEY is None and self.OIDC_OP_JWKS_ENDPOINT is None
        ):
            msg = "{} alg requires OIDC_RP_IDP_SIGN_KEY or OIDC_OP_JWKS_ENDPOINT to be configured."
            self.logger.error(msg.format(self.OIDC_RP_SIGN_ALGO))

        self.UserModel = get_user_model()

    def authenticate(self, request):
        print("CustomOIDCBackend.authenticate")

        # try to authenticate the user
        user = super().authenticate(request=request)

        if user is not None:
            return user

        # no match found
        return None

    def filter_users_by_claims(self, claims):
        """Override this method to filter users by claims"""
        # TODO : do we let admin user define which claim
        # shoud be used as reconciliation ?
        # for now, we use the sub claim
        print("CustomOIDCBackend.filter_users_by_claims")
        reconciliation = claims.get("sub")
        if not reconciliation:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(username=reconciliation)

    def create_user(self, claims):
        reconciliation = claims.get("sub")
        # username = self.get_username(claims)
        return self.UserModel.objects.create_user(username=reconciliation)
