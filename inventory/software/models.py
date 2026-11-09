import hashlib
import json

from asset.inventory_base.models import InventoryBase
from django.db import models
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template


class SoftwareMapping(models.Model):
    """map software fields to template fields"""

    template = models.ForeignKey(
        Template,
        related_name="software_mappings",
        on_delete=models.CASCADE,
    )
    section = models.ForeignKey(
        Section,
        related_name="software_mappings",
        on_delete=models.CASCADE,
    )
    name = models.ForeignKey(
        Field,
        related_name="software_name_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    publisher = models.ForeignKey(
        Field,
        related_name="software_publisher_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    version = models.ForeignKey(
        Field,
        related_name="software_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    major_version = models.ForeignKey(
        Field,
        related_name="software_major_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    minor_version = models.ForeignKey(
        Field,
        related_name="software_minor_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    patch_version = models.ForeignKey(
        Field,
        related_name="software_patch_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # Read per software row, from a field of the mapping's section
    architecture = models.ForeignKey(
        Field,
        related_name="software_architecture_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    package_format = models.ForeignKey(
        Field,
        related_name="software_package_format_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    source_package = models.ForeignKey(
        Field,
        related_name="software_source_package_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # Version of the source package: a binary package can carry another
    # version than its source (libldb2 2:2.11.0+samba4.22.11 from samba 2:4.22.11)
    source_version = models.ForeignKey(
        Field,
        related_name="software_source_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    package_origin = models.ForeignKey(
        Field,
        related_name="software_package_origin_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # Read once per machine, from a field of any section of the template
    os_id = models.ForeignKey(
        Field,
        related_name="software_os_id_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    os_like = models.ForeignKey(
        Field,
        related_name="software_os_like_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    os_release = models.ForeignKey(
        Field,
        related_name="software_os_release_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    os_codename = models.ForeignKey(
        Field,
        related_name="software_os_codename_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    running_kernel = models.ForeignKey(
        Field,
        related_name="software_running_kernel_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )


# What makes two installed software the same dictionary entry
SIGNATURE_FIELDS = (
    "name",
    "publisher",
    "version",
    "major_version",
    "minor_version",
    "patch_version",
    "platform_family",
    "platform_key",
    "architecture",
    "package_format",
    "source_package",
    "source_version",
    "package_origin",
)


def signature_of(values):
    """
    sha256 of the signature fields of an entry, from a dict or an instance:
    unique in the table, so that two inventories received at once cannot
    create the same entry twice. None and "" differ, as in the fields.
    """
    get = values.get if isinstance(values, dict) else lambda n: getattr(values, n)
    parts = [None if get(name) is None else str(get(name)) for name in SIGNATURE_FIELDS]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


class SoftwareDictionary(models.Model):
    """Aggregate which assets have a specific software signature"""

    name = models.TextField(blank=True, null=True)
    publisher = models.TextField(blank=True, null=True)
    version = models.CharField(max_length=128, blank=True, null=True)
    major_version = models.IntegerField(blank=True, null=True)
    minor_version = models.IntegerField(blank=True, null=True)
    patch_version = models.IntegerField(blank=True, null=True)
    platform_family = models.CharField(max_length=16, blank=True, null=True)
    platform_key = models.CharField(max_length=64, blank=True, null=True)
    architecture = models.CharField(max_length=64, blank=True, null=True)
    package_format = models.CharField(max_length=64, blank=True, null=True)
    source_package = models.CharField(max_length=255, blank=True, null=True)
    source_version = models.CharField(max_length=128, blank=True, null=True)
    package_origin = models.CharField(max_length=128, blank=True, null=True)
    installation_number = models.IntegerField(default=0)
    assets = models.ManyToManyField(
        InventoryBase,
        related_name="software_dictionary_entries",
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    # signature_of() the fields above, set on every save
    signature = models.CharField(max_length=64, unique=True, null=True, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["publisher"]),
            models.Index(fields=["version"]),
            models.Index(fields=["platform_key"]),
        ]

    def save(self, *args, **kwargs):
        self.signature = signature_of(self)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "signature" not in update_fields:
            kwargs["update_fields"] = [*update_fields, "signature"]
        super().save(*args, **kwargs)


class DistroRelease(models.Model):
    """Debian family release, turns an os-release codename into a version"""

    base = models.CharField(max_length=32)
    version = models.CharField(max_length=16)
    codename = models.CharField(max_length=32)
    # End of the standard support (Ubuntu): from then on, the release's
    # packages are also checked against its Ubuntu Pro advisories
    standard_support_end = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["base", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["base", "codename"], name="unique_distro_release_codename"
            )
        ]


class AssetPlatform(models.Model):
    """
    Platform of an asset, resolved from the OS values its software mapping points to
    """

    asset = models.OneToOneField(
        InventoryBase, related_name="platform", on_delete=models.CASCADE
    )
    os_id = models.CharField(max_length=255, blank=True, default="")
    os_like = models.CharField(max_length=255, blank=True, default="")
    os_release = models.CharField(max_length=255, blank=True, default="")
    os_codename = models.CharField(max_length=255, blank=True, default="")
    running_kernel = models.CharField(max_length=255, blank=True, default="")
    family = models.CharField(max_length=16, blank=True, default="")
    key = models.CharField(max_length=64, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
