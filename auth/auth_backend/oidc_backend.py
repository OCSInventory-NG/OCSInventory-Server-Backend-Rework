import logging

from auth.auth_config.models import AuthConfig
from auth.auth_mapping.models import AuthMapping
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class CustomOIDCBackend(OIDCAuthenticationBackend):
    """
    This backend extends the OIDCAuthenticationBackend from mozilla-django-oidc to allow
    dynamic configuration of the OIDC server and use of field mappings.
    """

    logger = logging.getLogger(__name__)
    # internal field used for reconciliation
    user_reconciliation_field = "username"

    def __init__(self):
        try:
            self.configs = AuthConfig.objects.filter(
                auth_method__name="OIDC", enabled=True
            ).order_by("priority")

            if not self.configs.exists():
                self.logger.error("No enabled OIDC configuration found")
                return

            self.mappings = AuthMapping.objects.filter(
                auth_config__enabled=True, auth_config__auth_method__name="OIDC"
            )

            # dict mapping external fields to internal fields.
            self.field_mappings = {
                mapping.internal_field: mapping.external_field for mapping in self.mappings
            }

            # TODO : get the first enabled config for now but figure out
            # how to handle multiple configs (or prevent it)
            oidc_config = self.configs[0]
            self.current_config = oidc_config
            self.logger.info(
                "Using OIDC config %s",
                oidc_config.id,
            )

            if len(self.mappings) == 0:
                self.logger.info(
                    "OIDC config %s has no mapping defined",
                    oidc.config.id,
                )

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

        except Exception as e:
            self.logger.exception(e)

    def filter_users_by_claims(self, claims):
        """
        Override mozilla_django_oidc filter_users_by_claims method
        Return all users matching the reconciliation field
        """

        try:
            reconciliation = self.get_user_reconciliation(claims)

            self.logger.debug(
                "Filtering OIDC users by field '%s' with value '%s'",
                self.user_reconciliation_field,
                reconciliation,
            )

            if not reconciliation:
                return self.UserModel.objects.none()
            return self.UserModel.objects.filter(
                **{self.user_reconciliation_field: reconciliation}
            )

        except Exception as e:
            self.logger.exception(e)
            return self.UserModel.objects.none()

    def create_user(self, claims):
        """Overriding mozilla_django_oidc create_user method"""
        try:
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
            return self.UserModel.objects.create_user(
                **{self.user_reconciliation_field: reconciliation}, **user_data
            )
        
        except Exception as e:
            self.logger.error("Failed to create user")
            self.logger.exception(e)
            return None

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
        try:
            # using user_reconciliation_field as reconciliation field
            reconciliation_mapping = self.field_mappings.get(self.user_reconciliation_field)
            if reconciliation_mapping:
                # default to using the 'sub' claim if the claim is not found
                self.logger.info(
                    "Reconciliation field found for internal field '%s'",
                    self.user_reconciliation_field,
                )
                reconciliation = claims.get(reconciliation_mapping, claims.get("sub"))
            else:
                # if no mapping defined, or no mapping matches the reconciliation field
                # then we default to using the 'sub' claim
                self.logger.info(
                    f"No mapping found for internal field '{self.user_reconciliation_field}"
                    "'. Defaulting to using the 'sub' claim for reconciliation."
                )
                reconciliation = claims.get("sub")

            if not reconciliation:
                raise ValueError(
                    "Failed to find a reconciliation value from the OIDC"
                    " claims or from the configured mappings."
                )

            return reconciliation

        except Exception as e:
            self.logger.exception(e)

    @staticmethod
    def get_config_fields():
        """
        Return the list of fields to be used in the 'config' field of the
        AuthConfig model.
        """
        return [
            "AUTHORIZATION_ENDPOINT",
            "TOKEN_ENDPOINT",
            "USERINFO_ENDPOINT",
            "JWKS_ENDPOINT",
            "CLIENT_ID",
            "CLIENT_SECRET",
            "SIGN_ALGO",
            "SCOPES",
            "PROXY",
            "AUTO_REDIRECT",
        ]

    def get_or_create_user(self, access_token, id_token, payload):
        """Override to attach auth profile metadata."""
        self.logger.debug(
            "OIDC authentication attempt started",
        )

        try:
            user_info = self.get_userinfo(access_token, id_token, payload)
            self.logger.info(
                "User info retrieved: %s",
                list(user_info.keys()),
            )

            claims_verified = self.verify_claims(user_info)
            if not claims_verified:
                self.logger.debug(
                    "OIDC claims verification failed with %s",
                    self.describe_user_by_claims(user_info),
                )
                raise SuspiciousOperation("Claims verification failed")

            users = self.filter_users_by_claims(user_info)

            if len(users) == 1:
                self.logger.debug(
                    "Local OIDC user found: %s (ID: %s)",
                    users[0].get_username(),
                    users[0].pk,
                )
                user = self.update_user(users[0], user_info)
            elif len(users) > 1:
                raise SuspiciousOperation("Multiple users returned")
            elif self.get_settings("OIDC_CREATE_USER", True):
                user = self.create_user(user_info)
                if user:
                    self.logger.debug(
                        "OIDC user created successfully: '%s' (ID: %s)",
                        user.get_username(),
                        user.pk,
                    )
                else:
                    self.logger.error("OIDC user creation failed")
            else:
                self.logger.info(
                    "Login failed: No user with %s found, and OIDC_CREATE_USER is False",
                    self.describe_user_by_claims(user_info),
                )
                return None

            if user:
                try:
                    metadata = {
                        "claims": user_info,
                        "token_payload": payload,
                        "requested_scopes": self.current_config.config.get("SCOPES"),
                    }
                    user._auth_context_data = {
                        "auth_method": self.current_config.auth_method,
                        "auth_config": self.current_config,
                        "metadata": metadata,
                    }
    
                except Exception as e:
                    self.logger.warning("Failed to attach metadata to authenticated user")
                    self.logger.exception(e)

            self.logger.info(
                "User authenticated successfully (Internal ID: %s)",
                user.pk,
            )
            return user

        except Exception as e:
            self.logger.debug(
                "User authentication failed with %s",
                user_info,
            )
            self.logger.exception(e)
            return None
