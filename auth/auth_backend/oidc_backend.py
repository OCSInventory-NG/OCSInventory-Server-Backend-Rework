from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from auth.auth_config.models import AuthConfig
from auth.auth_mapping.models import AuthMapping
from django.conf import settings
import logging
from django.contrib.auth import get_user_model


class CustomOIDCBackend(OIDCAuthenticationBackend):
    """
    This backend extends the OIDCAuthenticationBackend from mozilla-django-oidc to allow
    dynamic configuration of the OIDC server and use of field mappings.
    """
    logger = logging.getLogger(__name__)
    # internal field used for reconciliation
    user_reconciliation_field = "username"

    def __init__(self):

        self.configs = AuthConfig.objects.filter(auth_method__name="OIDC",
                                                 enabled=True).order_by("priority")
        self.mappings = AuthMapping.objects.filter(
                                                   auth_config__enabled=True,
                                                   auth_config__auth_method__name="OIDC"
                                                   )

        # dict mapping external fields to internal fields.
        self.field_mappings = {mapping.internal_field: mapping.external_field
                               for mapping in self.mappings}

        # TODO : get the first enabled config for now but figure out
        # how to handle multiple configs (or prevent it)
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
            msg = "{} alg requires OIDC_RP_IDP_SIGN_KEY or OIDC_OP_JWKS_ENDPOINT "
            "to be configured."
            self.logger.error(msg.format(self.OIDC_RP_SIGN_ALGO))

        self.UserModel = get_user_model()

    def filter_users_by_claims(self, claims):
        """
        Override mozilla_django_oidc filter_users_by_claims method
        Return all users matching the reconciliation field
        """

        reconciliation = self.get_user_reconciliation(claims)

        if not reconciliation:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(**{self.user_reconciliation_field:
                                                reconciliation})

    def create_user(self, claims):
        """Overriding mozilla_django_oidc create_user method"""
        reconciliation = self.get_user_reconciliation(claims)

        # populate the user data
        user_data = {}
        for internal, external in self.field_mappings.items():
            # reconciliation field is handled separately, we ignore it here
            if external != self.user_reconciliation_field:
                user_data[internal] = claims.get(external)

        # remove the reconciliation field from user_data to avoid duplicate arg
        user_data.pop(self.user_reconciliation_field, None)

        # create and return the user using the extracted data
        return self.UserModel.objects.create_user(**{
            self.user_reconciliation_field: reconciliation}, **user_data)

    def get_user_reconciliation(self, claims):
        """
        Custom method to get user reconciliation field from config's mappings
        Cases :
        - no mapping for the reconciliation field : use sub claim
        - mapping for the reconciliation field : use the external field mapped
            to the reconciliation field
        - no mappings for the config : use sub claim
        - mapped field not found in claims : use sub claim
        """
        # using user_reconciliation_field as reconciliation field
        reconciliation_mapping = self.field_mappings.get(
            self.user_reconciliation_field)
        if reconciliation_mapping:
            # default to using the 'sub' claim if the claim is not found
            reconciliation = claims.get(reconciliation_mapping, claims.get("sub"))
        else:
            # if no mapping defined, or no mapping matches the reconciliation field
            # then we default to using the 'sub' claim
            self.logger.debug(
                f"No mapping found for internal field '{self.user_reconciliation_field}"
                "'. Defaulting to using the 'sub' claim for reconciliation."
            )
            reconciliation = claims.get("sub")

        if not reconciliation:
            raise ValueError("Failed to find a reconciliation value from the OIDC"
                             " claims or from the configured mappings.")

        return reconciliation
