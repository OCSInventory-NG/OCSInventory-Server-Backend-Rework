from django.db import migrations

# Created inactive: an administrator turns them on
TASKS = [
    {
        "name": "securitySync.SecuritySync",
        "description": "Load the vulnerability data, then scan every machine",
        "recurrence": "daily",
        "hour": "02:00",
    },
    {
        "name": "vulnerabilityScan.VulnerabilityScan",
        "description": "Scan the machines inventoried since the last scan",
        "recurrence": "hourly",
        "hour": None,
    },
]


def seed(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    for task in TASKS:
        Scheduler.objects.update_or_create(
            name=task["name"],
            defaults={
                "active": False,
                "last_execution": None,
                "day_of_week": None,
                "day_of_month": None,
                "is_protected": True,
                **{key: value for key, value in task.items() if key != "name"},
            },
        )
    SecuritySettings = apps.get_model("security", "SecuritySettings")
    if not SecuritySettings.objects.exists():
        SecuritySettings.objects.create()


def unseed(apps, schema_editor):
    apps.get_model("scheduler", "Scheduler").objects.filter(
        name__in=[task["name"] for task in TASKS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0001_vulnerabilities"),
        ("scheduler", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
