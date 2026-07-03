from django.conf import settings
from django.db import models


# Create your models here.
class Template(models.Model):
    """
    Template model class definition

    The model will contain the following info
    - Name
    - Operating system
    - Last update
    - Is protected (used to prevent deletion from the console)
    """

    OS_CHOICES = (
        ("LEG", "Legacy"),
        ("DEB", "Linux (Debian based)"),
        ("RHEL", "Linux (RHEL based)"),
        ("MAC", "Mac"),
        ("WIN", "Windows"),
        ("SNMP", "SNMP"),
    )

    name = models.CharField(max_length=50)
    os = models.CharField(max_length=4, choices=OS_CHOICES, default="WIN")
    last_update = models.DateTimeField(auto_now=True)
    is_protected = models.BooleanField(default=False)


class TemplateVersion(models.Model):
    """
    TemplateVersion model class definition

    Stores a full, self-contained snapshot (name, os, is_protected and nested
    sections/fields) of a Template as it was right before a modification, so it
    can be listed and restored later.
    """

    template = models.ForeignKey(
        Template, related_name="versions", on_delete=models.CASCADE
    )
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    label = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def create_snapshot(cls, template, user=None, label=""):
        """
        Create a version snapshotting the template's current (pre-change) state,
        using the same shape as TemplateExportSerializer
        """
        from inventory.template.serializers import TemplateExportSerializer

        version = cls.objects.create(
            template=template,
            snapshot=TemplateExportSerializer(template).data,
            created_by=user if user and user.is_authenticated else None,
            label=label,
        )
        cls._trim_excess_versions(template)
        return version

    @classmethod
    def _trim_excess_versions(cls, template):
        """
        Delete the oldest versions of the template beyond the configured
        "max_template_versions" limit (config.Config, "server" group).
        A missing or non-positive value means no limit.
        """
        from config.models import Config

        server_config = Config.objects.filter(name="server").first()
        if not server_config:
            return

        max_versions = next(
            (
                item.get("value")
                for item in server_config.value
                if item.get("name") == "max_template_versions"
            ),
            None,
        )
        if not max_versions or max_versions <= 0:
            return

        stale_ids = (
            cls.objects.filter(template=template)
            .order_by("-created_at")
            .values_list("id", flat=True)[max_versions:]
        )
        if stale_ids:
            cls.objects.filter(id__in=list(stale_ids)).delete()
