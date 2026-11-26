"""FIRST EPSS scores: probability of exploitation in the next 30 days."""

import csv
import gzip
import io

from django.db import transaction
from security.models import EpssScore

BATCH = 5000
MIN_SHARE = 0.5


def load(path):
    """Replaces the scores from the daily gzip CSV. Returns (count, details)."""
    details = {}
    scores = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        first = handle.readline()
        if first.startswith("#"):
            # #model_version:v2025.03.14,score_date:2026-11-01T00:00:00+0000
            for part in first[1:].strip().split(","):
                key, _, value = part.partition(":")
                details[key.strip()] = value.strip()
            reader = csv.DictReader(handle)
        else:
            reader = csv.DictReader(io.StringIO(first + handle.read()))
        for row in reader:
            cve = (row.get("cve") or "").strip()
            try:
                score = float(row.get("epss") or "")
                percentile = float(row.get("percentile") or "")
            except ValueError:
                continue
            if cve.startswith("CVE-"):
                scores.append(EpssScore(cve=cve, score=score, percentile=percentile))
    current = EpssScore.objects.count()
    if not scores or len(scores) < MIN_SHARE * current:
        raise ValueError(
            f"EPSS scores refused: {len(scores)} scores against {current} loaded"
        )
    with transaction.atomic():
        EpssScore.objects.all().delete()
        EpssScore.objects.bulk_create(scores, batch_size=BATCH)
    return len(scores), details
