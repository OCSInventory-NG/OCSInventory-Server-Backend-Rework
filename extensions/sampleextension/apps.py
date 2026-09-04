# Example: an automation hook.
#
# The automation engine builds a "context" dict for each trigger from a
# resolver. Here we wrap the resolver for "inventory_received" so a rule
# can read sample.comments_count - without changing the automation app.

import logging

from django.apps import AppConfig

logger = logging.getLogger("extensions.sampleextension")


class SampleCommentsResolver:
    schema = {"sample": {"comments_count": {"type": "integer"}}}

    def __init__(self, base_resolver):
        self.base_resolver = base_resolver

    def build(self, instance):
        from extensions.sampleextension.models import SampleComment

        data = self.base_resolver.build(instance)
        data["sample"] = {"comments_count": SampleComment.objects.filter(asset=instance).count()}
        return data

    def get_schema(self):
        return {**self.base_resolver.get_schema(), **self.schema}


class SampleextensionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "extensions.sampleextension"
    verbose_name = "Sample Extension"

    def ready(self):
        # ready() runs once, when Django starts - the right place to
        # register something into a shared registry like this one.
        try:
            from automation.rule.context import (
                RESOLVER_REGISTRY,
                TRIGGER_DEFAULT_RESOLVERS,
                get_resolver_for_trigger,
            )

            base_resolver = get_resolver_for_trigger("inventory_received")
            if not isinstance(base_resolver, SampleCommentsResolver):
                slug = TRIGGER_DEFAULT_RESOLVERS["inventory_received"]
                RESOLVER_REGISTRY[slug] = SampleCommentsResolver(base_resolver)
        except Exception:
            logger.exception("sampleextension failed to initialize.")
