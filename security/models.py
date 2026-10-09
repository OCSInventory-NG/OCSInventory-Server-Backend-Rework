from django.db import models

SOURCE_OSV = "osv"
SOURCE_NVD = "nvd"
SOURCE_CHOICES = ((SOURCE_OSV, SOURCE_OSV), (SOURCE_NVD, SOURCE_NVD))

METHOD_OSV = "osv"
METHOD_NVD_RANGE = "nvd_range"
METHOD_NVD_ALL_VERSIONS = "nvd_all_versions"
METHOD_CHOICES = tuple(
    (method, method)
    for method in (METHOD_OSV, METHOD_NVD_RANGE, METHOD_NVD_ALL_VERSIONS)
)


class Vulnerability(models.Model):
    """A CVE, or an advisory without CVE, with the details of its source."""

    vuln_id = models.CharField(max_length=64, unique=True)
    summary = models.TextField(blank=True, default="")
    published = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)
    cvss_version = models.CharField(max_length=8, blank=True, default="")
    cvss_vector = models.CharField(max_length=255, blank=True, default="")
    cvss_score = models.FloatField(null=True, blank=True)
    # Debian urgency, Ubuntu priority, Rocky or Alma severity
    distro_rating = models.CharField(max_length=32, blank=True, default="")
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES)
    url = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)


class Finding(models.Model):
    """
    A product in a version affected by a vulnerability. (scheme, product,
    version) is the identity triple: machines are found through it when read.
    """

    vulnerability = models.ForeignKey(
        Vulnerability, related_name="findings", on_delete=models.CASCADE
    )
    scheme = models.CharField(max_length=8)
    product = models.CharField(max_length=511)
    version = models.CharField(max_length=128)
    advisory_id = models.CharField(max_length=64)
    # Empty when no fix is known
    fixed_version = models.CharField(max_length=255, blank=True, default="")
    affected_range = models.CharField(max_length=255, blank=True, default="")
    method = models.CharField(
        max_length=16, choices=METHOD_CHOICES, default=METHOD_OSV
    )
    uncertain = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "product", "version", "vulnerability"],
                name="unique_finding",
            )
        ]
        indexes = [models.Index(fields=["scheme", "product", "version"])]


class ProductCheck(models.Model):
    """
    When a product was last checked against a source. OSV key:
    "<ecosystem>|<name>|<version>"; NVD key: "vendor:product".
    """

    source = models.CharField(max_length=8, choices=SOURCE_CHOICES)
    key = models.CharField(max_length=512)
    checked_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    # NVD: the compact CVE list of the product, so that a new installed
    # version is evaluated without a new request
    payload = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "key"], name="unique_product_check"
            )
        ]
