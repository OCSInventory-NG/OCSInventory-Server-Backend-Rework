from django.conf import settings
from django.db import models


class CpeMatch(models.Model):
    """CPE matching decision for a software dictionary entry (at most one per software)."""

    SOURCE_AUTO = "auto_guessed"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [
        (SOURCE_AUTO, "Deviné automatiquement"),
        (SOURCE_MANUAL, "Saisi manuellement"),
    ]

    STATUS_NO_MATCH = "no_match"
    STATUS_PENDING_REVIEW = "pending_review"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_NO_MATCH, "Aucun CPE trouvé"),
        (STATUS_PENDING_REVIEW, "En attente de revue"),
        (STATUS_CONFIRMED, "Confirmé"),
        (STATUS_REJECTED, "Rejeté"),
    ]

    software = models.OneToOneField(
        "software.SoftwareDictionary",
        related_name="cpe_match",
        on_delete=models.CASCADE,
    )
    cpe = models.CharField(max_length=255, null=True, blank=True)
    cpe_rank = models.FloatField(null=True, blank=True)
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NO_MATCH
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_cpe_matches",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.software.name} -> {self.cpe or '(aucun)'} [{self.status}]"


class CveReport(models.Model):
    """A single CVE associated with a software dictionary entry (many per software)."""

    VERSION_MATCH_MATCHED = "matched"
    VERSION_MATCH_UNKNOWN = "unknown"
    VERSION_MATCH_CHOICES = [
        (VERSION_MATCH_MATCHED, "Version installée confirmée dans la plage affectée"),
        (VERSION_MATCH_UNKNOWN, "Plage affectée non comparable (CVE conservée par défaut)"),
    ]

    software = models.ForeignKey(
        "software.SoftwareDictionary",
        related_name="cve_reports",
        on_delete=models.CASCADE,
    )
    cve_id = models.CharField(max_length=32)
    cvss_score = models.FloatField(null=True, blank=True)
    published_date = models.DateField(null=True, blank=True)
    version_match = models.CharField(
        max_length=10,
        choices=VERSION_MATCH_CHOICES,
        default=VERSION_MATCH_UNKNOWN,
    )
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-cvss_score"]
        constraints = [
            models.UniqueConstraint(
                fields=["software", "cve_id"], name="unique_cve_per_software"
            )
        ]

    def __str__(self):
        return f"{self.cve_id} ({self.software.name})"
