# Example: a CLI command ("python manage.py sample_comment_stats").
# Django auto-discovers it here, no registration needed. It also reads
# config.json - an extension's own static settings file, next to
# extension.json, read directly from disk (no admin UI for it).

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from extensions.sampleextension.models import SampleComment

_CONFIG = json.loads((Path(__file__).resolve().parents[2] / "config.json").read_text())


class Command(BaseCommand):
    help = "Print how many sample comments exist and how many assets have at least one."

    def handle(self, *args, **options):
        total = SampleComment.objects.count()
        assets = SampleComment.objects.values("asset_id").distinct().count()
        self.stdout.write(
            self.style.SUCCESS(
                f"{total} {_CONFIG['stats_label']} on {assets} asset(s)."
            )
        )
