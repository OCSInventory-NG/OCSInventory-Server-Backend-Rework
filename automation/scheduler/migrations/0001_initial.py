from django.db import migrations, models


def create_default_automations(apps, schema_editor):
    """
    Create default automation tasks
    """
    Scheduler = apps.get_model("scheduler", "Scheduler")

    Scheduler.objects.create(
        name="dynaGroups.DynaGroups",
        description="Dynamic groups generation",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour="01:00",
        day_of_week=None,
        day_of_month=None,
        is_protected=True,
    )

    Scheduler.objects.create(
        name="adminDataGeneration.AdminDataGeneration",
        description="Administrative data generation",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour="01:00",
        day_of_week=None,
        day_of_month=None,
        is_protected=True,
    )

    Scheduler.objects.create(
        name="purgeAgentLog.PurgeAgentLog",
        description="Purge agent logs",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour="01:00",
        day_of_week=None,
        day_of_month=None,
        is_protected=True,
    )

    Scheduler.objects.create(
        name="mergeLegacy.MergeLegacy",
        description="Merge legacy assets",
        active=True,
        recurrence="monthly",
        last_execution=None,
        hour=None,
        day_of_week=None,
        day_of_month=1,
        is_protected=True,
    )

    Scheduler.objects.create(
        name="purgeFiles.PurgeFiles",
        description="Purge orphaned files",
        active=True,
        recurrence="monthly",
        last_execution=None,
        hour=None,
        day_of_week=None,
        day_of_month=1,
        is_protected=True,
    )

    Scheduler.objects.create(
        name="purgePackages.PurgePackages",
        description="Purge old packages",
        active=True,
        recurrence="monthly",
        last_execution=None,
        hour=None,
        day_of_week=None,
        day_of_month=1,
        is_protected=True,
    )

    Scheduler.objects.create(
        name="ipdiscoverScan.IpDiscoverScan",
        description="Scan networks for devices with IpDiscover",
        active=True,
        recurrence="weekly",
        last_execution=None,
        hour="02:00",
        day_of_week=5,
        day_of_month=None,
    )


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Scheduler",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.CharField(max_length=1024)),
                ("active", models.BooleanField()),
                (
                    "recurrence",
                    models.CharField(
                        choices=[
                            ("hourly", "hourly"),
                            ("daily", "daily"),
                            ("weekly", "weekly"),
                            ("monthly", "monthly"),
                        ],
                        default="daily",
                        max_length=7,
                    ),
                ),
                ("last_execution", models.DateTimeField(null=True)),
                ("hour", models.TimeField(blank=True, null=True)),
                ("day_of_week", models.IntegerField(blank=True, null=True)),
                ("day_of_month", models.IntegerField(blank=True, null=True)),
                ("is_protected", models.BooleanField(default=False)),
            ],
        ),
        migrations.RunPython(create_default_automations),
    ]
