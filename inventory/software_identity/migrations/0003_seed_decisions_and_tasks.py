from django.db import migrations

# Generic corrections found while measuring on the dev fleet
SHIPPED_DECISIONS = [
    ("windows", "microsoft edge", "microsoft:edge_chromium"),
    ("macos", "microsoft edge", "microsoft:edge_chromium"),
    ("windows", "git", "git-scm:git"),
    ("windows", "microsoft .net sdk from visual studio", "microsoft:.net"),
    ("macos", "idle", "python:python"),
    ("macos", "python launcher", "python:python"),
]

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
    IdentityDecision = apps.get_model("software_identity", "IdentityDecision")
    IdentityDecision.objects.bulk_create(
        [
            IdentityDecision(
                family=family, match_key=key, product=product, source="shipped"
            )
            for family, key, product in SHIPPED_DECISIONS
        ]
    )
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
    apps.get_model("software_identity", "IdentityDecision").objects.filter(
        source="shipped"
    ).delete()
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
