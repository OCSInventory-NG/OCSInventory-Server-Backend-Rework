"""
Vulnerability data held locally, the evaluation of each software identity
against it, and the exposures of the machines.

Source data (OSV advisories, NVD CVEs, KEV, EPSS) is loaded by security.sync.
An identity (scheme, product, version, platform key, extended) is evaluated
once (Evaluation and its Finding rows), then copied to the machines that have
it installed (Exposure). Exclusions are applied when reading, never stored on
the exposures.
"""

from asset.asset_group.models import AssetGroup
from asset.inventory_base.models import InventoryBase
from django.conf import settings
from django.db import models
from django.db.models import Q
from inventory.software.models import SoftwareDictionary

# Sources, each synchronized on its own
SOURCE_OSV_DEBIAN = "osv_debian"
SOURCE_OSV_UBUNTU = "osv_ubuntu"
SOURCE_OSV_ROCKY = "osv_rocky"
SOURCE_OSV_ALMA = "osv_alma"
SOURCE_NVD = "nvd"
SOURCE_KEV = "kev"
SOURCE_EPSS = "epss"
OSV_SOURCES = (SOURCE_OSV_DEBIAN, SOURCE_OSV_UBUNTU, SOURCE_OSV_ROCKY, SOURCE_OSV_ALMA)
SOURCES = OSV_SOURCES + (SOURCE_NVD, SOURCE_KEV, SOURCE_EPSS)
SOURCE_CHOICES = tuple((source, source) for source in SOURCES)

METHOD_OSV = "osv"
METHOD_NVD_RANGE = "nvd_range"
METHOD_NVD_EXACT = "nvd_exact"
METHOD_NVD_ALL_VERSIONS = "nvd_all_versions"
METHOD_CHOICES = tuple(
    (method, method)
    for method in (
        METHOD_OSV,
        METHOD_NVD_RANGE,
        METHOD_NVD_EXACT,
        METHOD_NVD_ALL_VERSIONS,
    )
)

# Where the fix comes from: the distribution, or its Ubuntu Pro repositories
CHANNEL_STANDARD = ""
CHANNEL_UBUNTU_PRO = "ubuntu_pro"

# Why an exposure was closed, in the order they are tried
RESOLUTION_FIXED = "fixed"
RESOLUTION_UNINSTALLED = "uninstalled"
RESOLUTION_WITHDRAWN = "withdrawn"
RESOLUTION_IDENTITY_CHANGED = "identity_changed"
RESOLUTION_OUT_OF_WINDOW = "out_of_window"
RESOLUTIONS = (
    RESOLUTION_FIXED,
    RESOLUTION_UNINSTALLED,
    RESOLUTION_WITHDRAWN,
    RESOLUTION_IDENTITY_CHANGED,
    RESOLUTION_OUT_OF_WINDOW,
)
RESOLUTION_CHOICES = tuple((resolution, resolution) for resolution in RESOLUTIONS)


class SourceSync(models.Model):
    """
    State of a source. A failed synchronization keeps the previous data; a
    source without success for STALE_AFTER is stale.
    """

    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, unique=True)
    last_attempt = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    # What tells a changed file: ETag, Last-Modified, sha256 per feed
    fingerprint = models.JSONField(default=dict, blank=True)
    record_count = models.IntegerField(default=0)
    # OSV: the ecosystems that have advisories (a release still followed)
    details = models.JSONField(default=dict, blank=True)


class OsvAdvisory(models.Model):
    """
    An OSV record. Detection records (DEBIAN-CVE, UBUNTU-CVE, RLSA, ALSA) carry
    the affected packages; the others (DSA, DLA, USN) are references only.
    """

    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    advisory_id = models.CharField(max_length=128, unique=True)
    detection = models.BooleanField(default=True)
    cves = models.JSONField(default=list)
    summary = models.TextField(blank=True, default="")
    published = models.DateTimeField(null=True, blank=True)
    modified = models.CharField(max_length=64, blank=True, default="")
    withdrawn = models.BooleanField(default=False)
    cvss_vector = models.CharField(max_length=255, blank=True, default="")
    # Ubuntu priority, Rocky or Alma severity
    rating = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["source", "detection"])]


class OsvAdvisoryCve(models.Model):
    """The CVEs of an advisory, to find the references of a CVE."""

    advisory = models.ForeignKey(
        OsvAdvisory, related_name="cve_links", on_delete=models.CASCADE
    )
    cve = models.CharField(max_length=64, db_index=True)


class OsvAffected(models.Model):
    """A package of an ecosystem affected by an advisory, its ranges as events."""

    advisory = models.ForeignKey(
        OsvAdvisory, related_name="affected", on_delete=models.CASCADE
    )
    ecosystem = models.CharField(max_length=64)
    package = models.CharField(max_length=255)
    # [[{"introduced": "0"}, {"fixed": "1.2-3"}], ...]: one list per range
    ranges = models.JSONField(default=list)
    versions = models.JSONField(default=list)
    # Debian urgency
    urgency = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["ecosystem", "package"])]


class NvdCve(models.Model):
    """
    A CVE of the NVD. Inside the loaded years: with its CPE matches. Older:
    its scores only, for the severity of distribution advisories.
    """

    cve_id = models.CharField(max_length=32, unique=True)
    year = models.IntegerField(db_index=True)
    full = models.BooleanField(default=True)
    rejected = models.BooleanField(default=False)
    published = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    cvss3_vector = models.CharField(max_length=255, blank=True, default="")
    cvss3_score = models.FloatField(null=True, blank=True)
    cvss4_vector = models.CharField(max_length=255, blank=True, default="")
    cvss4_score = models.FloatField(null=True, blank=True)


class NvdMatch(models.Model):
    """A vulnerable CPE match of a CVE configuration."""

    cve = models.ForeignKey(NvdCve, related_name="matches", on_delete=models.CASCADE)
    vendor_product = models.CharField(max_length=511, db_index=True)
    criteria = models.CharField(max_length=1024)
    bounds = models.JSONField(default=dict, blank=True)
    # Vulnerable only with another product (an AND with an operating system)
    conditional = models.BooleanField(default=False)


class KevEntry(models.Model):
    """A CVE of the CISA Known Exploited Vulnerabilities catalog."""

    cve = models.CharField(max_length=32, unique=True)
    date_added = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    ransomware = models.BooleanField(default=False)


class EpssScore(models.Model):
    """Probability of exploitation in the next 30 days (FIRST EPSS)."""

    cve = models.CharField(max_length=32, unique=True)
    score = models.FloatField()
    percentile = models.FloatField()


class Vulnerability(models.Model):
    """
    A CVE (or an advisory without CVE) found on an evaluated identity, with
    what the priority reads: retained score, KEV, EPSS.
    """

    vuln_id = models.CharField(max_length=128, unique=True)
    summary = models.TextField(blank=True, default="")
    published = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)
    # Retained score: CVSS 3.x, else 4.0 (NVD first, then the advisory)
    cvss_version = models.CharField(max_length=8, blank=True, default="")
    cvss_vector = models.CharField(max_length=255, blank=True, default="")
    cvss_score = models.FloatField(null=True, blank=True)
    # Distribution rating, when the advisories carry one
    distro_rating = models.CharField(max_length=32, blank=True, default="")
    kev = models.BooleanField(default=False)
    kev_date_added = models.DateField(null=True, blank=True)
    epss = models.FloatField(null=True, blank=True)
    epss_percentile = models.FloatField(null=True, blank=True)
    url = models.CharField(max_length=255, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)


class Evaluation(models.Model):
    """
    An identity checked against the local data: Linux packages per platform
    (and per Ubuntu Pro repository), applications per product and version.
    """

    scheme = models.CharField(max_length=8)
    product = models.CharField(max_length=511)
    version = models.CharField(max_length=128)
    platform_key = models.CharField(max_length=64, blank=True, default="")
    # A package of an extended support repository (Ubuntu Pro)
    extended = models.BooleanField(default=False)
    evaluated_at = models.DateTimeField()
    # Sources read, with the time of their data: {source: last_success}
    sources = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "product", "version", "platform_key", "extended"],
                name="unique_evaluation",
            )
        ]


class Finding(models.Model):
    """A vulnerability of an evaluated identity."""

    evaluation = models.ForeignKey(
        Evaluation, related_name="findings", on_delete=models.CASCADE
    )
    vulnerability = models.ForeignKey(
        Vulnerability, related_name="findings", on_delete=models.CASCADE
    )
    advisory_id = models.CharField(max_length=128)
    # Empty when no fix is known
    fixed_version = models.CharField(max_length=255, blank=True, default="")
    fix_channel = models.CharField(max_length=16, blank=True, default="")
    affected_range = models.CharField(max_length=255, blank=True, default="")
    method = models.CharField(max_length=16, choices=METHOD_CHOICES)
    uncertain = models.BooleanField(default=False)
    # Debian urgency, Ubuntu priority, Rocky or Alma severity
    rating = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "vulnerability"], name="unique_finding"
            )
        ]


class Exposure(models.Model):
    """
    A vulnerability of a product installed on a machine, from its first
    detection to its resolution. The product (scheme, product) is the key:
    a new version of it fixes or keeps the exposure.
    """

    asset = models.ForeignKey(
        InventoryBase, related_name="exposures", on_delete=models.CASCADE
    )
    vulnerability = models.ForeignKey(
        Vulnerability, related_name="exposures", on_delete=models.CASCADE
    )
    entry = models.ForeignKey(
        SoftwareDictionary,
        related_name="exposures",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    scheme = models.CharField(max_length=8)
    product = models.CharField(max_length=511)
    # Software as installed, kept when the dictionary entry goes away
    software_name = models.CharField(max_length=255, blank=True, default="")
    version = models.CharField(max_length=128)
    platform_family = models.CharField(max_length=16, blank=True, default="")
    advisory_id = models.CharField(max_length=128, blank=True, default="")
    fixed_version = models.CharField(max_length=255, blank=True, default="")
    fix_channel = models.CharField(max_length=16, blank=True, default="")
    method = models.CharField(max_length=16, choices=METHOD_CHOICES)
    uncertain = models.BooleanField(default=False)
    kernel = models.BooleanField(default=False)
    rating = models.CharField(max_length=32, blank=True, default="")
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(
        max_length=16, choices=RESOLUTION_CHOICES, blank=True, default=""
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "scheme", "product", "vulnerability"],
                condition=Q(closed_at__isnull=True),
                name="unique_open_exposure",
            )
        ]
        indexes = [
            models.Index(fields=["asset", "closed_at"]),
            models.Index(fields=["vulnerability", "closed_at"]),
        ]


class Exclusion(models.Model):
    """
    A vulnerability (or the whole scan) left out for a machine or a group.
    Applied when reading; an expired exclusion no longer applies.
    """

    vuln_id = models.CharField(max_length=128, blank=True, default="")
    asset = models.ForeignKey(
        InventoryBase,
        related_name="security_exclusions",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    group = models.ForeignKey(
        AssetGroup,
        related_name="security_exclusions",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    comment = models.TextField()
    expires_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(asset__isnull=False, group__isnull=True)
                    | Q(asset__isnull=True, group__isnull=False)
                ),
                name="exclusion_one_target",
            )
        ]


PRIORITY_CRITERIA = ("kev", "score", "epss", "machines")


def default_priority():
    return list(PRIORITY_CRITERIA)


class SecuritySettings(models.Model):
    """Single row: what the scan loads and how the vulnerabilities are ordered."""

    # NVD: the years of CVE identifiers loaded, the current one included
    nvd_years = models.PositiveSmallIntegerField(default=3)
    # Order of the vulnerability list, first criterion first
    priority = models.JSONField(default=default_priority)
    # Windows and macOS identities: CPE match above, review between
    cpe_match_score = models.FloatField(default=0.9)
    cpe_review_score = models.FloatField(default=0.5)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.order_by("id").first() or cls()


class ScanLock(models.Model):
    """One synchronization or scan at a time; a lock older than 12 h is taken over."""

    name = models.CharField(max_length=32, unique=True)
    holder = models.CharField(max_length=128, blank=True, default="")
    acquired_at = models.DateTimeField()


class ScanState(models.Model):
    """Single row: when the scans last ran."""

    last_full_scan = models.DateTimeField(null=True, blank=True)
    last_incremental_scan = models.DateTimeField(null=True, blank=True)

    @classmethod
    def current(cls):
        return cls.objects.order_by("id").first() or cls.objects.create()
