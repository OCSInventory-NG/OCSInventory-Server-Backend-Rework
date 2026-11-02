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

# The "security" section of the general configuration, as security.config
# defines it at this migration
SECTION = "security"
ITEMS = [
    {
        "name": "nvd_years",
        "description": "Years of NVD vulnerabilities loaded for Windows and "
        "macOS software, the current one included",
        "value": 3,
        "type": "number input",
        "unit": "years",
        "min": 1,
        "max": 25,
    },
    {
        "name": "priority",
        "description": "Order of the vulnerability list, first criterion first",
        "value": ["kev", "score", "epss", "machines"],
        "type": "ordered list",
        "unit": "",
        "options": ["kev", "score", "epss", "machines"],
    },
    {
        "name": "cpe_match_score",
        "description": "Windows and macOS software: name match score from "
        "which the product is identified automatically",
        "value": 0.9,
        "type": "number input",
        "unit": "",
        "min": 0,
        "max": 1,
    },
    {
        "name": "cpe_review_score",
        "description": "Windows and macOS software: name match score from "
        "which the product is proposed for review",
        "value": 0.5,
        "type": "number input",
        "unit": "",
        "min": 0,
        "max": 1,
    },
]


def seed(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    Config = apps.get_model("config", "Config")
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
    Config.objects.get_or_create(name=SECTION, defaults={"value": ITEMS})


def unseed(apps, schema_editor):
    apps.get_model("scheduler", "Scheduler").objects.filter(
        name__in=[task["name"] for task in TASKS]
    ).delete()
    apps.get_model("config", "Config").objects.filter(name=SECTION).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0001_initial"),
        ("scheduler", "0001_initial"),
        ("config", "0004_legacy_reconciliation"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
