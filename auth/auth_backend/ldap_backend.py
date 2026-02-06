import logging

import ldap
from auth.auth_config.models import AuthConfig
from auth.auth_mapping.models import AuthMapping
from django.contrib.auth.models import Group
from django_auth_ldap.backend import LDAPBackend
from django_auth_ldap.config import LDAPSearch


class CustomLDAPBackend(LDAPBackend):
    """
    This backend extends the LDAPBackend from django-auth-ldap to allow
    dynamic configuration of the LDAP server.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        super(CustomLDAPBackend, self).__init__()
        # get all LDAP config from database
        self.configs = AuthConfig.objects.filter(
            auth_method__name="LDAP", enabled=True
        ).order_by("priority")
        # and mappings
        self.mappings = AuthMapping.objects.filter(
            auth_config__enabled=True, auth_config__auth_method__name="LDAP"
        )

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            for config in self.configs:
                # set settings
                self.settings.SERVER_URI = config.config["SERVER_URI"]
                self.settings.BIND_DN = config.config["BIND_DN"]
                self.settings.BIND_PASSWORD = config.config["BIND_PASSWORD"]
                mirror_groups_enabled = bool(config.config.get("MIRROR_GROUPS"))
                # we mirror groups from memberOf
                self.settings.MIRROR_GROUPS = False

                self.settings.USER_SEARCH = LDAPSearch(
                    config.config["BASE_DN"],
                    ldap.SCOPE_SUBTREE,
                    f"({config.config['USER_LOGIN_FIELD']}=%(user)s)",
                )

                self.defineMapping(config)
                ldap.set_option(
                    ldap.OPT_PROTOCOL_VERSION, config.config["PROTOCOL_VERSION"]
                )

                # attempt authentication
                user = super(CustomLDAPBackend, self).authenticate(
                    request, username=username, password=password, **kwargs
                )

                if user:
                    if mirror_groups_enabled:
                        self._mirror_memberof_groups(user)

                    metadata = self._build_metadata(user)
                    user._auth_context_data = {
                        "auth_method": config.auth_method,
                        "auth_config": config,
                        "metadata": metadata,
                    }
                    return user

        except Exception as e:
            self.logger.exception(e)
            return None

    def defineMapping(self, config):
        for mapping in self.mappings:
            self.settings.USER_ATTR_MAP[mapping.internal_field] = mapping.external_field

        # if empty mapping is defined, inform user
        if len(self.settings.USER_ATTR_MAP) == 0:
            self.logger.info(f"LDAP config {config.id} has no mapping defined")

    @staticmethod
    def get_config_fields():
        """
        Return the list of fields to be used in the 'config' field of the
        AuthConfig model.
        """
        return [
            "SERVER_URI",
            "BIND_DN",
            "BIND_PASSWORD",
            "BASE_DN",
            "USER_LOGIN_FIELD",
            "PROTOCOL_VERSION",
            "MIRROR_GROUPS",
        ]

    def _build_metadata(self, user):
        metadata = {}
        ldap_user = getattr(user, "ldap_user", None)
        if not ldap_user:
            return metadata

        attrs = ldap_user.attrs or {}
        sanitized_attrs = {}
        for key, value in attrs.items():
            sanitized_attrs[key] = [
                v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else v
                for v in value
            ]

        metadata["dn"] = ldap_user.dn
        metadata["memberOf"] = [
            (
                entry.decode("utf-8", errors="ignore")
                if isinstance(entry, bytes)
                else entry
            )
            for entry in sanitized_attrs.get("memberOf", [])
        ]
        metadata["attributes"] = sanitized_attrs
        return metadata

    def _mirror_memberof_groups(self, user):
        ldap_user = getattr(user, "ldap_user", None)
        if ldap_user is None:
            self.logger.warning(
                "LDAP user data not available for %s; skipping group mirroring",
                user.get_username(),
            )
            return

        attrs = getattr(ldap_user, "attrs", None)
        if attrs is None:
            self.logger.warning(
                "LDAP attributes not available for %s; skipping group mirroring",
                user.get_username(),
            )
            return

        found, member_of = self._get_memberof_attr(attrs)
        if not found:
            return

        if not member_of:
            user.groups.clear()
            return

        group_names = self._memberof_to_group_names(member_of)
        if not group_names:
            user.groups.clear()
            return

        groups = self._get_or_create_groups(group_names)
        user.groups.set(groups)

    @staticmethod
    def _get_memberof_attr(attrs):
        if "memberOf" in attrs:
            return True, attrs.get("memberOf")
        for key, value in attrs.items():
            if isinstance(key, bytes):
                key = key.decode("utf-8", errors="ignore")
            if str(key).lower() == "memberof":
                return True, value
        return False, None

    @staticmethod
    def _memberof_to_group_names(member_of):
        if isinstance(member_of, (bytes, str)):
            values = [member_of]
        else:
            values = list(member_of)

        group_names = set()
        for value in values:
            name = CustomLDAPBackend._group_name_from_memberof(value)
            if name:
                group_names.add(name)

        return sorted(group_names)

    @staticmethod
    def _group_name_from_memberof(value):
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        value = str(value).strip()
        if not value:
            return None

        if "=" in value:
            try:
                parts = ldap.dn.explode_dn(value, notypes=1)
            except ldap.LDAPError:
                return None
            if parts:
                return parts[0].strip()

        return value

    @staticmethod
    def _get_or_create_groups(group_names):
        groups = []
        for name in group_names:
            group, _ = Group.objects.get_or_create(name=name)
            groups.append(group)
        return groups


