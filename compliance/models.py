from asset.inventory_base.models import InventoryBase
from django.db import models


class WindowsBuildMapping(models.Model):
    build = models.IntegerField(unique=True, help_text="Windows build number (e.g. 22621)")
    channel = models.CharField(max_length=20, help_text="endoflife.date channel slug (e.g. 22h2)")

    class Meta:
        ordering = ["build"]

    def __str__(self):
        return f"{self.build} → {self.channel}"


class ComplianceType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ComplianceRule(models.Model):
    SEVERITY_CRITICAL = "critical"
    SEVERITY_HIGH = "high"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_LOW = "low"
    SEVERITY_CHOICES = [
        (SEVERITY_CRITICAL, "Critical"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_LOW, "Low"),
    ]

    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=50)
    severity = models.CharField(max_length=50, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
    logic = models.JSONField()
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"[{self.type}] {self.name}"


class ComplianceResult(models.Model):
    STATUS_COMPLIANT = "compliant"
    STATUS_NON_COMPLIANT = "non_compliant"
    STATUS_UNKNOWN = "unknown"
    STATUS_CHOICES = [
        (STATUS_COMPLIANT, "Compliant"),
        (STATUS_NON_COMPLIANT, "Non-compliant"),
        (STATUS_UNKNOWN, "Unknown"),
    ]

    asset = models.ForeignKey(
        InventoryBase, related_name="compliance_results", on_delete=models.CASCADE
    )
    rule = models.ForeignKey(
        ComplianceRule, related_name="results", on_delete=models.CASCADE
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    detail = models.JSONField(null=True, blank=True)
    evaluated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-evaluated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "rule"], name="unique_compliance_result_per_asset_rule"
            )
        ]

    def __str__(self):
        return f"{self.asset.name} / {self.rule.name} → {self.status}"


class EOLCache(models.Model):
    product    = models.CharField(max_length=100)
    cycle      = models.CharField(max_length=50)
    eol        = models.CharField(max_length=20, null=True, blank=True)
    is_eol     = models.BooleanField(default=False)
    support    = models.BooleanField(default=False)
    latest     = models.CharField(max_length=50, null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "cycle"], name="unique_eol_cache_product_cycle"
            )
        ]

    def __str__(self):
        return f"{self.product}/{self.cycle} → eol={self.eol}"


class AssetEOLStatus(models.Model):
    asset      = models.OneToOneField(
        InventoryBase, related_name="eol_status", on_delete=models.CASCADE
    )
    product    = models.CharField(max_length=100, null=True, blank=True)
    cycle      = models.CharField(max_length=50, null=True, blank=True)
    eol        = models.CharField(max_length=20, null=True, blank=True)
    is_eol     = models.BooleanField(default=False)
    support    = models.BooleanField(default=False)
    latest     = models.CharField(max_length=50, null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset"]

    def __str__(self):
        return f"{self.asset.name} → {self.product}/{self.cycle} eol={self.eol}"


class CustomEOLExtendedSupport(models.Model):
    product = models.CharField(
        max_length=100,
        help_text="endoflife.date product slug (e.g. ubuntu)",
    )
    cycle = models.CharField(
        max_length=50,
        help_text="Version cycle (e.g. 22.04)",
    )
    is_extended = models.BooleanField(
        default=True,
        help_text="Whether purchased extended support is active for this product/cycle",
    )

    class Meta:
        ordering = ["product", "cycle"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "cycle"],
                name="unique_custom_eol_product_cycle",
            )
        ]

    def __str__(self):
        return f"{self.product}/{self.cycle} → is_extended={self.is_extended}"
