import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models

# Created inactive: an administrator turns them on
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

# Origins whose packages their distribution's advisories cover, and whether
# they are an extended support repository (Ubuntu Pro: esm-infra, esm-apps).
# Left out on purpose: "Fedora Project" (on a RHEL rebuild it means EPEL; a
# Fedora fleet adds the row), LinuxMint, Pop!_OS, Docker, Google...: third
# party.
PACKAGE_ORIGINS = [
    ("Debian", "debian", False),
    ("Ubuntu", "ubuntu", False),
    ("Rocky Enterprise Software Foundation", "rocky", False),
    ("AlmaLinux", "almalinux", False),
    ("Red Hat, Inc.", "redhat", False),
    ("CentOS", "centos", False),
    ("UbuntuESM", "ubuntu", True),
    ("UbuntuESMApps", "ubuntu", True),
]

# "microsoft:edge" is the EdgeHTML browser (CVEs of 2016 to 2018 for every
# version): today's Edge is microsoft:edge_chromium
DECISIONS = [
    ("windows", "microsoft edge", "microsoft:edge_chromium"),
    ("macos", "microsoft edge", "microsoft:edge_chromium"),
]

# Products the NVD files under two names
ALIASES = [
    ("zoom:zoom", "zoom:meetings"),
    ("zoom:meetings", "zoom:zoom"),
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
    PackageOrigin = apps.get_model("software_identity", "PackageOrigin")
    IdentityDecision = apps.get_model("software_identity", "IdentityDecision")
    CpeAlias = apps.get_model("software_identity", "CpeAlias")

    for task in TASKS:
        Scheduler.objects.create(
            active=False,
            last_execution=None,
            day_of_week=None,
            day_of_month=None,
            is_protected=True,
            **task,
        )
    PackageOrigin.objects.bulk_create(
        [
            PackageOrigin(name=name, distribution=distribution, extended=extended)
            for name, distribution, extended in PACKAGE_ORIGINS
        ]
    )
    IdentityDecision.objects.bulk_create(
        [
            IdentityDecision(
                family=family, match_key=key, product=product, source="shipped"
            )
            for family, key, product in DECISIONS
        ]
    )
    CpeAlias.objects.bulk_create(
        [
            CpeAlias(product=product, alias=alias, source="shipped")
            for product, alias in ALIASES
        ]
    )


def unseed(apps, schema_editor):
    apps.get_model("scheduler", "Scheduler").objects.filter(
        name__in=[task["name"] for task in TASKS]
    ).delete()
    apps.get_model("software_identity", "PackageOrigin").objects.filter(
        name__in=[name for name, _, _ in PACKAGE_ORIGINS]
    ).delete()
    apps.get_model("software_identity", "IdentityDecision").objects.filter(
        source="shipped"
    ).delete()
    apps.get_model("software_identity", "CpeAlias").objects.filter(
        source="shipped"
    ).delete()
    check_constraints_now(schema_editor)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("scheduler", "0001_initial"),
        ("software", "0007_software_identity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CpeIndexState",
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
                ("version", models.IntegerField(default=0)),
                (
                    "source_sha256",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                (
                    "source_date",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("synced_at", models.DateTimeField(blank=True, null=True)),
                ("product_count", models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="CpeAlias",
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
                ("product", models.CharField(max_length=511)),
                ("alias", models.CharField(max_length=511)),
                (
                    "source",
                    models.CharField(
                        choices=[("shipped", "shipped"), ("admin", "admin")],
                        default="admin",
                        max_length=8,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("product", "alias"), name="unique_cpe_alias"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="CpeProduct",
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
                ("vendor", models.CharField(max_length=255)),
                ("product", models.CharField(max_length=255)),
                ("titles", models.JSONField(default=dict)),
                ("versions", models.JSONField(default=list)),
                ("popularity", models.IntegerField(default=0)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("vendor", "product"), name="unique_cpe_product"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="CpeToken",
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
                ("token", models.CharField(db_index=True, max_length=255)),
                ("weight", models.FloatField()),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tokens",
                        to="software_identity.cpeproduct",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="IdentityDecision",
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
                    "family",
                    models.CharField(
                        choices=[("windows", "windows"), ("macos", "macos")],
                        max_length=16,
                    ),
                ),
                ("match_key", models.CharField(max_length=255)),
                ("product", models.CharField(blank=True, max_length=511, null=True)),
                (
                    "source",
                    models.CharField(
                        choices=[("shipped", "shipped"), ("admin", "admin")],
                        default="admin",
                        max_length=8,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
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
        ),
        migrations.CreateModel(
            name="PackageOrigin",
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
                ("name", models.CharField(max_length=128)),
                ("distribution", models.CharField(max_length=32)),
                ("extended", models.BooleanField(default=False)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("name"),
                        name="unique_package_origin_name",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="SoftwareIdentity",
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
                ("family", models.CharField(blank=True, default="", max_length=16)),
                ("match_key", models.CharField(blank=True, default="", max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("matched", "matched"),
                            ("validated", "validated"),
                            ("review", "review"),
                            ("none", "none"),
                            ("unsupported", "unsupported"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reason", models.CharField(blank=True, default="", max_length=32)),
                ("scheme", models.CharField(blank=True, default="", max_length=8)),
                ("identifier", models.TextField(blank=True, default="")),
                ("product", models.CharField(blank=True, default="", max_length=511)),
                ("version", models.CharField(blank=True, default="", max_length=128)),
                ("score", models.FloatField(blank=True, null=True)),
                ("candidates", models.JSONField(default=list)),
                ("index_version", models.IntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "decision",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="identities",
                        to="software_identity.identitydecision",
                    ),
                ),
                (
                    "entry",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identity",
                        to="software.softwaredictionary",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="identitydecision",
            constraint=models.UniqueConstraint(
                fields=("family", "match_key", "source"),
                name="unique_identity_decision",
            ),
        ),
        migrations.AddIndex(
            model_name="softwareidentity",
            index=models.Index(
                fields=["family", "match_key"], name="software_id_family_2e75df_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="softwareidentity",
            index=models.Index(fields=["status"], name="software_id_status_c84a4b_idx"),
        ),
        migrations.AddIndex(
            model_name="softwareidentity",
            index=models.Index(
                fields=["product"], name="software_id_product_8d824d_idx"
            ),
        ),
        migrations.RunPython(seed, reverse_code=unseed),
    ]
