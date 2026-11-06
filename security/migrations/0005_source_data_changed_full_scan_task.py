from django.db import migrations, models
from django.db.models import F

SYNC = "securitySync.SecuritySync"
SYNC_DESCRIPTIONS = (
    "Load the vulnerability data, then scan every machine",
    "Load the vulnerability data and refresh the scores",
)
FULL_SCAN = {
    "name": "vulnerabilityFullScan.VulnerabilityFullScan",
    "description": "Scan every machine against the vulnerability data",
    "recurrence": "weekly",
    # Sunday (Monday is 0), after the daily data load at 02:00
    "day_of_week": 6,
    "hour": "03:00",
}


def split_sync_and_scan(apps, schema_editor):
    SourceSync = apps.get_model("security", "SourceSync")
    Scheduler = apps.get_model("scheduler", "Scheduler")
    # The evaluations made so far recorded the last success as data version
    SourceSync.objects.filter(data_changed_at__isnull=True).update(
        data_changed_at=F("last_success")
    )
    Scheduler.objects.filter(name=SYNC).update(description=SYNC_DESCRIPTIONS[1])
    # Created inactive, like the other security tasks
    Scheduler.objects.get_or_create(
        name=FULL_SCAN["name"],
        defaults={
            "active": False,
            "last_execution": None,
            "day_of_month": None,
            "is_protected": True,
            **{key: value for key, value in FULL_SCAN.items() if key != "name"},
        },
    )


def join_sync_and_scan(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    Scheduler.objects.filter(name=FULL_SCAN["name"]).delete()
    Scheduler.objects.filter(name=SYNC).update(description=SYNC_DESCRIPTIONS[0])


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0004_reevaluate_cpe_platform"),
        ("scheduler", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourcesync",
            name="data_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(split_sync_and_scan, join_sync_and_scan),
    ]
