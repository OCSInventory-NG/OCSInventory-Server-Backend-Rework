import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_cve_enrichment_task(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    Scheduler.objects.create(
        name="cveEnrichment.CveEnrichment",
        description="Resolve CPE and fetch CVEs for software dictionary entries",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour="04:00",
        day_of_week=None,
        day_of_month=None,
        is_protected=True,
    )


def unseed_cve_enrichment_task(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    Scheduler.objects.filter(name="cveEnrichment.CveEnrichment").delete()


def seed_cve_integration_config(apps, schema_editor):
    from security.config import CVE_CONFIG_ITEMS

    Config = apps.get_model("config", "Config")
    Config.objects.create(name="cve_integration", value=CVE_CONFIG_ITEMS)


def unseed_cve_integration_config(apps, schema_editor):
    Config = apps.get_model("config", "Config")
    Config.objects.filter(name="cve_integration").delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("software", "0006_legacy"),
        ("scheduler", "0001_initial"),
        ("config", "0004_legacy_reconciliation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CpeMatch",
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
                ("cpe", models.CharField(blank=True, max_length=255, null=True)),
                ("cpe_rank", models.FloatField(blank=True, null=True)),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("auto_guessed", "Deviné automatiquement"),
                            ("manual", "Saisi manuellement"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("no_match", "Aucun CPE trouvé"),
                            ("pending_review", "En attente de revue"),
                            ("confirmed", "Confirmé"),
                            ("rejected", "Rejeté"),
                        ],
                        default="no_match",
                        max_length=20,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_cpe_matches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "software",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpe_match",
                        to="software.softwaredictionary",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="CveReport",
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
                ("cve_id", models.CharField(max_length=32)),
                ("cvss_score", models.FloatField(blank=True, null=True)),
                ("published_date", models.DateField(blank=True, null=True)),
                ("fetched_at", models.DateTimeField(auto_now=True)),
                (
                    "software",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cve_reports",
                        to="software.softwaredictionary",
                    ),
                ),
            ],
            options={
                "ordering": ["-cvss_score"],
            },
        ),
        migrations.AddConstraint(
            model_name="cvereport",
            constraint=models.UniqueConstraint(
                fields=("software", "cve_id"), name="unique_cve_per_software"
            ),
        ),
        migrations.RunPython(
            seed_cve_enrichment_task,
            reverse_code=unseed_cve_enrichment_task,
        ),
        migrations.RunPython(
            seed_cve_integration_config,
            reverse_code=unseed_cve_integration_config,
        ),
    ]
