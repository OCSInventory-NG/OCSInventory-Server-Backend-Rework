from django.db import migrations, models


def create_default_automations(apps, schema_editor):
    """
    Create default automation tasks
    """
    Scheduler = apps.get_model("scheduler", "Scheduler")

    Scheduler.objects.create(
        name="DynaGroups.DynaGroups",
        description="Dynamic Groups Generation",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour=None,
        day_of_week=None,
        day_of_month=None,
    )

    Scheduler.objects.create(
        name="AccountInfoGeneration.AccountInfoGeneration",
        description="Account Info Generation",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour=None,
        day_of_week=None,
        day_of_month=None,
    )
    
    Scheduler.objects.create(
        name="PurgeAgentLog.PurgeAgentLog",
        description="Log Agent Purge",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour=None,
        day_of_week=None,
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
                ("hour", models.IntegerField(blank=True, null=True)),
                ("day_of_week", models.IntegerField(blank=True, null=True)),
                ("day_of_month", models.IntegerField(blank=True, null=True)),
            ],
        ),
        migrations.RunPython(create_default_automations),
    ]
