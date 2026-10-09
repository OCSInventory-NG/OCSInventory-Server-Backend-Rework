from django.db import migrations

TASK = {
    "name": "vulnerabilityScan.VulnerabilityScan",
    "description": "Check identified software against OSV and the NVD",
    "recurrence": "hourly",
    "hour": None,
}


def seed(apps, schema_editor):
    apps.get_model("scheduler", "Scheduler").objects.create(
        active=False,
        last_execution=None,
        day_of_week=None,
        day_of_month=None,
        is_protected=True,
        **TASK,
    )


def unseed(apps, schema_editor):
    apps.get_model("scheduler", "Scheduler").objects.filter(name=TASK["name"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0001_vulnerabilities"),
        ("scheduler", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
