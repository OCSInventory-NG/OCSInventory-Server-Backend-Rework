"""CISA Known Exploited Vulnerabilities catalog."""

import json

from django.db import transaction
from django.utils.dateparse import parse_date
from security.models import KevEntry

BATCH = 2000
MIN_SHARE = 0.5


def load(path):
    """Replaces the catalog. Returns (entry count, details)."""
    with open(path, encoding="utf-8") as handle:
        catalog = json.load(handle)
    entries = {}
    for item in catalog.get("vulnerabilities") or []:
        cve = (item.get("cveID") or "").strip()
        if cve.startswith("CVE-"):
            entries[cve] = KevEntry(
                cve=cve,
                date_added=parse_date(item.get("dateAdded") or ""),
                due_date=parse_date(item.get("dueDate") or ""),
                ransomware=(item.get("knownRansomwareCampaignUse") or "").lower()
                == "known",
            )
    current = KevEntry.objects.count()
    if not entries or len(entries) < MIN_SHARE * current:
        raise ValueError(
            f"KEV catalog refused: {len(entries)} entries against {current} loaded"
        )
    with transaction.atomic():
        KevEntry.objects.all().delete()
        KevEntry.objects.bulk_create(entries.values(), batch_size=BATCH)
    return len(entries), {"catalog_version": catalog.get("catalogVersion", "")}
