import logging
from copy import deepcopy
from typing import Dict


LOGGER = logging.getLogger(__name__)

FIELD_STRING = {"type": "string"}
FIELD_INTEGER = {"type": "integer"}
FIELD_OBJECT = {"type": "object"}


class BaseContextResolver:
    """Builds the JSON Logic context for a trigger"""

    slug = "default"
    schema = {}

    def build(self, instance) -> Dict:
        data = getattr(instance, "__dict__", {}).copy()
        # not needed for rules
        data.pop("_state", None)
        return data

    def get_schema(self) -> Dict:
        """Return extra fields this resolver adds"""
        return self.schema


class UserLoginContextResolver(BaseContextResolver):
    slug = "user_login"
    schema = {
        "auth_profile": {
            "auth_method": FIELD_INTEGER,
            "auth_config": FIELD_INTEGER,
            "metadata": FIELD_OBJECT,
        }
    }

    def build(self, instance):
        """Fetch context for the user login trigger"""
        context = super().build(instance)
        runtime_context = getattr(instance, "_auth_context_data", None)
        if runtime_context:
            auth_method = runtime_context.get("auth_method")
            auth_config = runtime_context.get("auth_config")
            profile_data = {
                "auth_method": self.extract_id(auth_method),
                "auth_config": self.extract_id(auth_config),
                "metadata": deepcopy(runtime_context.get("metadata") or {}),
            }
            context["auth_profile"] = profile_data
        return context

    @staticmethod
    def extract_id(value):
        if isinstance(value, int):
            return value
        return getattr(value, "id", None)


class InventoryReceivedContextResolver(BaseContextResolver):
    slug = "inventory_received"
    schema = {
        "template": {
            "id": FIELD_INTEGER,
            "name": FIELD_STRING,
        }
    }

    def build(self, instance):
        """Fetch context for the inventory received trigger"""
        context = super().build(instance)
        template = getattr(instance, "template", None)
        if template:
            context["template"] = {
                "id": template.id,
                "name": template.name,
            }
        return context


class NetdeviceReceivedContextResolver(BaseContextResolver):
    slug = "netdevice_received"
    schema = {
        "network": {
            "id": FIELD_INTEGER,
            "nettag": FIELD_STRING,
            "name": FIELD_STRING,
            "location": FIELD_STRING,
            "group_id": FIELD_INTEGER,
        }
    }

    def build(self, instance):
        """Fetch context for the netdevice received trigger"""
        context = super().build(instance)
        network = getattr(instance, "network", None)
        if network:
            context["network"] = {
                "id": network.id,
                "nettag": getattr(network, "nettag", ""),
                "name": network.name,
                "location": network.location,
                "group_id": network.group_id,
            }
        return context


RESOLVER_REGISTRY = {
    BaseContextResolver.slug: BaseContextResolver(),
    UserLoginContextResolver.slug: UserLoginContextResolver(),
    InventoryReceivedContextResolver.slug: InventoryReceivedContextResolver(),
    NetdeviceReceivedContextResolver.slug: NetdeviceReceivedContextResolver(),
}

TRIGGER_DEFAULT_RESOLVERS = {
    "user_login": UserLoginContextResolver.slug,
    "inventory_received": InventoryReceivedContextResolver.slug,
    "netdevice_received": NetdeviceReceivedContextResolver.slug,
}


def get_resolver(slug: str) -> BaseContextResolver:
    return RESOLVER_REGISTRY.get(slug, RESOLVER_REGISTRY[BaseContextResolver.slug])


def get_resolver_for_trigger(trigger: str) -> BaseContextResolver:
    slug = TRIGGER_DEFAULT_RESOLVERS.get(trigger, BaseContextResolver.slug)
    return get_resolver(slug)
