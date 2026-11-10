import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Created inactive: an administrator turns them on
TASKS = [
    {
        "name": "securitySync.SecuritySync",
        "description": "Load the vulnerability data and refresh the scores",
        "recurrence": "daily",
        "hour": "02:00",
    },
    {
        "name": "vulnerabilityScan.VulnerabilityScan",
        "description": "Scan the machines inventoried since the last scan",
        "recurrence": "hourly",
        "hour": None,
    },
    {
        "name": "vulnerabilityFullScan.VulnerabilityFullScan",
        "description": "Scan every machine against the vulnerability data",
        "recurrence": "weekly",
        # Sunday (Monday is 0), after the daily data load at 02:00
        "day_of_week": 6,
        "hour": "03:00",
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


def check_constraints_now(schema_editor):
    """
    PostgreSQL alters no table with deferred constraint checks pending in
    the transaction: the schema operations of this migration come after.
    """
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


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
                **task,
                "is_protected": True,
            },
        )
    Config.objects.get_or_create(name=SECTION, defaults={"value": ITEMS})


def unseed(apps, schema_editor):
    apps.get_model("scheduler", "Scheduler").objects.filter(
        name__in=[task["name"] for task in TASKS]
    ).delete()
    apps.get_model("config", "Config").objects.filter(name=SECTION).delete()
    check_constraints_now(schema_editor)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("config", "0004_legacy_reconciliation"),
        ("scheduler", "0001_initial"),
        ("asset_group", "0002_initial"),
        ("inventory_base", "0001_initial"),
        ("software", "0006_legacy"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EpssScore",
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
                ("cve", models.CharField(max_length=32, unique=True)),
                ("score", models.FloatField()),
                ("percentile", models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name="KevEntry",
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
                ("cve", models.CharField(max_length=32, unique=True)),
                ("date_added", models.DateField(blank=True, null=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("ransomware", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="NvdCve",
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
                ("cve_id", models.CharField(max_length=32, unique=True)),
                ("year", models.IntegerField(db_index=True)),
                ("full", models.BooleanField(default=True)),
                ("rejected", models.BooleanField(default=False)),
                ("published", models.DateTimeField(blank=True, null=True)),
                ("modified", models.DateTimeField(blank=True, null=True)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "cvss3_vector",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("cvss3_score", models.FloatField(blank=True, null=True)),
                (
                    "cvss4_vector",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("cvss4_score", models.FloatField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="ScanLock",
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
                ("name", models.CharField(max_length=32, unique=True)),
                ("holder", models.CharField(blank=True, default="", max_length=128)),
                ("acquired_at", models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name="ScanState",
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
                ("last_full_scan", models.DateTimeField(blank=True, null=True)),
                ("last_incremental_scan", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="SourceSync",
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
                    "source",
                    models.CharField(
                        choices=[
                            ("osv_debian", "osv_debian"),
                            ("osv_ubuntu", "osv_ubuntu"),
                            ("osv_rocky", "osv_rocky"),
                            ("osv_alma", "osv_alma"),
                            ("osv_redhat", "osv_redhat"),
                            ("nvd", "nvd"),
                            ("kev", "kev"),
                            ("epss", "epss"),
                        ],
                        max_length=16,
                        unique=True,
                    ),
                ),
                ("last_attempt", models.DateTimeField(blank=True, null=True)),
                ("last_success", models.DateTimeField(blank=True, null=True)),
                ("data_changed_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("fingerprint", models.JSONField(blank=True, default=dict)),
                ("record_count", models.IntegerField(default=0)),
                ("details", models.JSONField(blank=True, default=dict)),
            ],
        ),
        migrations.CreateModel(
            name="Vulnerability",
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
                ("vuln_id", models.CharField(max_length=128, unique=True)),
                ("summary", models.TextField(blank=True, default="")),
                ("published", models.DateTimeField(blank=True, null=True)),
                ("modified", models.DateTimeField(blank=True, null=True)),
                (
                    "cvss_version",
                    models.CharField(blank=True, default="", max_length=8),
                ),
                (
                    "cvss_vector",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("cvss_score", models.FloatField(blank=True, null=True)),
                (
                    "distro_rating",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                ("kev", models.BooleanField(default=False)),
                ("kev_date_added", models.DateField(blank=True, null=True)),
                ("epss", models.FloatField(blank=True, null=True)),
                ("epss_percentile", models.FloatField(blank=True, null=True)),
                ("url", models.CharField(blank=True, default="", max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Evaluation",
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
                ("scheme", models.CharField(max_length=8)),
                ("product", models.CharField(max_length=511)),
                ("version", models.CharField(max_length=128)),
                (
                    "platform_key",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("extended", models.BooleanField(default=False)),
                ("evaluated_at", models.DateTimeField()),
                ("sources", models.JSONField(default=dict)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "scheme",
                            "product",
                            "version",
                            "platform_key",
                            "extended",
                        ),
                        name="unique_evaluation",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="NvdMatch",
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
                ("vendor_product", models.CharField(db_index=True, max_length=511)),
                ("criteria", models.CharField(max_length=1024)),
                ("bounds", models.JSONField(blank=True, default=dict)),
                ("conditional", models.BooleanField(default=False)),
                ("systems", models.JSONField(blank=True, default=list)),
                (
                    "cve",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matches",
                        to="security.nvdcve",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OsvAdvisory",
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
                    "source",
                    models.CharField(
                        choices=[
                            ("osv_debian", "osv_debian"),
                            ("osv_ubuntu", "osv_ubuntu"),
                            ("osv_rocky", "osv_rocky"),
                            ("osv_alma", "osv_alma"),
                            ("osv_redhat", "osv_redhat"),
                            ("nvd", "nvd"),
                            ("kev", "kev"),
                            ("epss", "epss"),
                        ],
                        max_length=16,
                    ),
                ),
                ("advisory_id", models.CharField(max_length=128, unique=True)),
                ("detection", models.BooleanField(default=True)),
                ("cves", models.JSONField(default=list)),
                ("summary", models.TextField(blank=True, default="")),
                ("published", models.DateTimeField(blank=True, null=True)),
                ("modified", models.CharField(blank=True, default="", max_length=64)),
                ("withdrawn", models.BooleanField(default=False)),
                (
                    "cvss_vector",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("rating", models.CharField(blank=True, default="", max_length=32)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["source", "detection"],
                        name="security_os_source_c7e868_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="OsvAdvisoryCve",
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
                ("cve", models.CharField(db_index=True, max_length=64)),
                (
                    "advisory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cve_links",
                        to="security.osvadvisory",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Exclusion",
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
                ("vuln_id", models.CharField(blank=True, default="", max_length=128)),
                ("comment", models.TextField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="security_exclusions",
                        to="inventory_base.inventorybase",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="security_exclusions",
                        to="asset_group.assetgroup",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("asset__isnull", False), ("group__isnull", True)),
                            models.Q(("asset__isnull", True), ("group__isnull", False)),
                            _connector="OR",
                        ),
                        name="exclusion_one_target",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="OsvAffected",
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
                ("ecosystem", models.CharField(max_length=64)),
                ("package", models.CharField(max_length=255)),
                ("ranges", models.JSONField(default=list)),
                ("versions", models.JSONField(default=list)),
                ("urgency", models.CharField(blank=True, default="", max_length=32)),
                (
                    "advisory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affected",
                        to="security.osvadvisory",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["ecosystem", "package"],
                        name="security_os_ecosyst_6d81e3_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Finding",
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
                ("advisory_id", models.CharField(max_length=128)),
                (
                    "fixed_version",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "fix_channel",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                (
                    "affected_range",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("osv", "osv"),
                            ("nvd_range", "nvd_range"),
                            ("nvd_exact", "nvd_exact"),
                        ],
                        max_length=16,
                    ),
                ),
                ("rating", models.CharField(blank=True, default="", max_length=32)),
                (
                    "evaluation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="findings",
                        to="security.evaluation",
                    ),
                ),
                (
                    "vulnerability",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="findings",
                        to="security.vulnerability",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("evaluation", "vulnerability"), name="unique_finding"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Exposure",
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
                ("scheme", models.CharField(max_length=8)),
                ("product", models.CharField(max_length=511)),
                (
                    "software_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("version", models.CharField(max_length=128)),
                (
                    "platform_family",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                (
                    "advisory_id",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "fixed_version",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "fix_channel",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("osv", "osv"),
                            ("nvd_range", "nvd_range"),
                            ("nvd_exact", "nvd_exact"),
                        ],
                        max_length=16,
                    ),
                ),
                ("kernel", models.BooleanField(default=False)),
                ("rating", models.CharField(blank=True, default="", max_length=32)),
                ("first_seen", models.DateTimeField()),
                ("last_seen", models.DateTimeField()),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "resolution",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("fixed", "fixed"),
                            ("uninstalled", "uninstalled"),
                            ("withdrawn", "withdrawn"),
                            ("identity_changed", "identity_changed"),
                            ("out_of_window", "out_of_window"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exposures",
                        to="inventory_base.inventorybase",
                    ),
                ),
                (
                    "entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="exposures",
                        to="software.softwaredictionary",
                    ),
                ),
                (
                    "vulnerability",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exposures",
                        to="security.vulnerability",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["asset", "closed_at"],
                        name="security_ex_asset_i_00e223_idx",
                    ),
                    models.Index(
                        fields=["vulnerability", "closed_at"],
                        name="security_ex_vulnera_db7d6b_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("closed_at__isnull", True)),
                        fields=("asset", "scheme", "product", "vulnerability"),
                        name="unique_open_exposure",
                    )
                ],
            },
        ),
        migrations.RunPython(seed, reverse_code=unseed),
    ]
