from django.conf import settings
from django.db import models
from inventory.software.models import SoftwareDictionary
from inventory.software_identity.normalizers.base import STATUSES


class CpeProduct(models.Model):
    """An application of the NVD CPE dictionary, with its titles and known versions"""

    vendor = models.CharField(max_length=255)
    product = models.CharField(max_length=255)
    titles = models.JSONField(default=dict)
    versions = models.JSONField(default=list)
    popularity = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "product"], name="unique_cpe_product"
            )
        ]

    @property
    def key(self):
        return f"{self.vendor}:{self.product}"


class CpeToken(models.Model):
    """A word of a product's titles, weighted by its rarity over the whole index"""

    token = models.CharField(max_length=255, db_index=True)
    product = models.ForeignKey(
        CpeProduct, related_name="tokens", on_delete=models.CASCADE
    )
    weight = models.FloatField()


class CpeIndexState(models.Model):
    """Single row describing the CPE index currently loaded"""

    version = models.IntegerField(default=0)
    source_sha256 = models.CharField(max_length=64, blank=True, default="")
    source_date = models.CharField(max_length=64, blank=True, default="")
    synced_at = models.DateTimeField(null=True, blank=True)
    product_count = models.IntegerField(default=0)

    @classmethod
    def current(cls):
        return cls.objects.first() or cls()


FAMILY_CHOICES = (("windows", "windows"), ("macos", "macos"))


class IdentityDecision(models.Model):
    """
    Catalog entry: the product of a Windows or macOS software name, for every
    version and machine. An admin decision overrides a shipped one.
    """

    SOURCE_SHIPPED = "shipped"
    SOURCE_ADMIN = "admin"
    SOURCE_CHOICES = ((SOURCE_SHIPPED, SOURCE_SHIPPED), (SOURCE_ADMIN, SOURCE_ADMIN))

    family = models.CharField(max_length=16, choices=FAMILY_CHOICES)
    match_key = models.CharField(max_length=255)
    # vendor:product of the CPE index, null means "no CPE"
    product = models.CharField(max_length=511, null=True, blank=True)
    source = models.CharField(
        max_length=8, choices=SOURCE_CHOICES, default=SOURCE_ADMIN
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["family", "match_key", "source"],
                name="unique_identity_decision",
            )
        ]


class SoftwareIdentity(models.Model):
    """Identity of a software dictionary entry: purl, CPE, or why there is none"""

    STATUS_CHOICES = tuple((status, status) for status in STATUSES)

    entry = models.OneToOneField(
        SoftwareDictionary, related_name="identity", on_delete=models.CASCADE
    )
    family = models.CharField(max_length=16, blank=True, default="")
    match_key = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    reason = models.CharField(max_length=32, blank=True, default="")
    scheme = models.CharField(max_length=8, blank=True, default="")
    identifier = models.TextField(blank=True, default="")
    product = models.CharField(max_length=511, blank=True, default="")
    version = models.CharField(max_length=128, blank=True, default="")
    score = models.FloatField(null=True, blank=True)
    candidates = models.JSONField(default=list)
    decision = models.ForeignKey(
        IdentityDecision,
        related_name="identities",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    index_version = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["family", "match_key"]),
            models.Index(fields=["status"]),
            models.Index(fields=["product"]),
        ]
