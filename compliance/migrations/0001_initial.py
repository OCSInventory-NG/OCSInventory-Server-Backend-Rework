import django.db.models.deletion
from django.db import migrations, models

_WINDOWS_BUILD_MAPPINGS = [
    (19044, "21h2"),
    (19045, "22h2"),
    (22000, "21h2"),
    (22621, "22h2"),
    (22631, "23h2"),
    (26100, "24h2"),
]


def seed_windows_build_mappings(apps, schema_editor):
    WindowsBuildMapping = apps.get_model("compliance", "WindowsBuildMapping")
    WindowsBuildMapping.objects.bulk_create([
        WindowsBuildMapping(build=build, channel=channel)
        for build, channel in _WINDOWS_BUILD_MAPPINGS
    ])


def unseed_windows_build_mappings(apps, schema_editor):
    WindowsBuildMapping = apps.get_model("compliance", "WindowsBuildMapping")
    WindowsBuildMapping.objects.filter(
        build__in=[b for b, _ in _WINDOWS_BUILD_MAPPINGS]
    ).delete()


def seed_default_rules(apps, schema_editor):
    ComplianceRule = apps.get_model("compliance", "ComplianceRule")
    ComplianceRule.objects.bulk_create([
        ComplianceRule(
            name="Required software installed",
            description="Example rule: checks that a required software is present on the asset. Edit the software name to match your environment.",
            type="software",
            severity="medium",
            priority=1,
            logic={"in": ["example-software", {"var": "softwares_names"}]},
            enabled=False,
        ),
    ])


def unseed_default_rules(apps, schema_editor):
    ComplianceRule = apps.get_model("compliance", "ComplianceRule")
    ComplianceRule.objects.filter(
        name__in=["OS not end-of-life", "OS EOL status known"]
    ).delete()


def seed_compliance_tasks(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    Scheduler.objects.create(
        name="complianceEvaluation.ComplianceEvaluation",
        description="Evaluate compliance rules against all assets",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour="03:00",
        day_of_week=None,
        day_of_month=None,
        is_protected=True,
    )
    Scheduler.objects.create(
        name="eolUpdate.EOLUpdate",
        description="Update OS end-of-life status for all assets",
        active=True,
        recurrence="daily",
        last_execution=None,
        hour="02:00",
        day_of_week=None,
        day_of_month=None,
        is_protected=True,
    )


def unseed_compliance_tasks(apps, schema_editor):
    Scheduler = apps.get_model("scheduler", "Scheduler")
    Scheduler.objects.filter(
        name__in=[
            "complianceEvaluation.ComplianceEvaluation",
            "eolUpdate.EOLUpdate",
        ]
    ).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("inventory_base", "0001_initial"),
        ("scheduler", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ComplianceRule",
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
                ("name", models.CharField(max_length=255)),
                ("description", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "type",
                    models.CharField(
                        choices=[("software", "Software"), ("security", "Security")],
                        max_length=50,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("critical", "Critical"),
                            ("high", "High"),
                            ("medium", "Medium"),
                            ("low", "Low"),
                        ],
                        default="medium",
                        max_length=50,
                    ),
                ),
                ("priority", models.IntegerField()),
                ("logic", models.JSONField()),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["priority"],
            },
        ),
        migrations.CreateModel(
            name="CustomEOLExtendedSupport",
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
                (
                    "product",
                    models.CharField(
                        help_text="endoflife.date product slug (e.g. ubuntu)",
                        max_length=100,
                    ),
                ),
                (
                    "cycle",
                    models.CharField(
                        help_text="Version cycle (e.g. 22.04)",
                        max_length=50,
                    ),
                ),
                (
                    "extended_support_until",
                    models.DateField(
                        help_text="Purchased extended support end date",
                    ),
                ),
                ("label", models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                "ordering": ["product", "cycle"],
            },
        ),
        migrations.CreateModel(
            name="EOLCache",
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
                ("product", models.CharField(max_length=100)),
                ("cycle", models.CharField(max_length=50)),
                ("eol", models.CharField(blank=True, max_length=20, null=True)),
                ("is_eol", models.BooleanField(default=False)),
                ("support", models.CharField(blank=True, max_length=20, null=True)),
                ("latest", models.CharField(blank=True, max_length=50, null=True)),
                ("fetched_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="WindowsBuildMapping",
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
                (
                    "build",
                    models.IntegerField(
                        help_text="Windows build number (e.g. 22621)",
                        unique=True,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        help_text="endoflife.date channel slug (e.g. 22h2)",
                        max_length=20,
                    ),
                ),
            ],
            options={
                "ordering": ["build"],
            },
        ),
        migrations.CreateModel(
            name="AssetEOLStatus",
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
                (
                    "asset",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="eol_status",
                        to="inventory_base.inventorybase",
                    ),
                ),
                ("product", models.CharField(blank=True, max_length=100, null=True)),
                ("cycle", models.CharField(blank=True, max_length=50, null=True)),
                ("eol", models.CharField(blank=True, max_length=20, null=True)),
                ("is_eol", models.BooleanField(default=False)),
                ("support", models.CharField(blank=True, max_length=20, null=True)),
                ("latest", models.CharField(blank=True, max_length=50, null=True)),
                ("fetched_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["asset"],
            },
        ),
        migrations.CreateModel(
            name="ComplianceResult",
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
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compliance_results",
                        to="inventory_base.inventorybase",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="compliance.compliancerule",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("compliant", "Compliant"),
                            ("non_compliant", "Non-compliant"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=50,
                    ),
                ),
                ("detail", models.JSONField(blank=True, null=True)),
                ("evaluated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-evaluated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="customeolextendedsupport",
            constraint=models.UniqueConstraint(
                fields=("product", "cycle"),
                name="unique_custom_eol_product_cycle",
            ),
        ),
        migrations.AddConstraint(
            model_name="eolcache",
            constraint=models.UniqueConstraint(
                fields=("product", "cycle"),
                name="unique_eol_cache_product_cycle",
            ),
        ),
        migrations.AddConstraint(
            model_name="complianceresult",
            constraint=models.UniqueConstraint(
                fields=("asset", "rule"),
                name="unique_compliance_result_per_asset_rule",
            ),
        ),
        migrations.RunPython(
            seed_windows_build_mappings,
            reverse_code=unseed_windows_build_mappings,
        ),
        migrations.RunPython(
            seed_default_rules,
            reverse_code=unseed_default_rules,
        ),
        migrations.RunPython(
            seed_compliance_tasks,
            reverse_code=unseed_compliance_tasks,
        ),
    ]
