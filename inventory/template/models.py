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
        ("VIRT", "Virtualization"),
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
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    label = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "revision"], name="unique_template_revision"
            )
        ]

    @classmethod
    def create_snapshot(cls, template, user=None, label=""):
        """
        Create a version snapshotting the template's current state, including
        the primary keys of the nested sections/fields (see
        TemplateSnapshotSerializer) so a rollback can restore by id. The
        revision number increments per template (1, 2, 3, ...) and is never
        reused, even if older versions get deleted.
        """
        from inventory.template.serializers import TemplateSnapshotSerializer

        last_revision = (
            cls.objects.filter(template=template)
            .aggregate(models.Max("revision"))
            .get("revision__max")
            or 0
        )

        return cls.objects.create(
            template=template,
            revision=last_revision + 1,
            snapshot=TemplateSnapshotSerializer(template).data,
            created_by=user if user and user.is_authenticated else None,
            label=label,
        )
