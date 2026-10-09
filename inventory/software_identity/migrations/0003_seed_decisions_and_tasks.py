from django.db import migrations

# No shipped decision for now: whether a release ships a sample of
# decisions is decided before the release.

TASKS = [
    {
        "name": "cpeIndex.CpeIndexSync",
        "description": "Refresh the CPE index from the NVD CPE dictionary",
        "recurrence": "daily",
        "hour": "01:00",
    },
    {
        "name": "softwareIdentity.SoftwareIdentity",
        "description": "Identify new or outdated software dictionary entries",
        "recurrence": "hourly",
        "hour": None,
    },
]


def seed(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    for task in TASKS:
        Scheduler.objects.create(
            active=False,
            last_execution=None,
            day_of_week=None,
            day_of_month=None,
            is_protected=True,
            **task,
        )


def unseed(apps, schema_editor):
    apps.get_model("scheduler", "Scheduler").objects.filter(
        name__in=[task["name"] for task in TASKS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("software_identity", "0002_identity"),
        ("scheduler", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
