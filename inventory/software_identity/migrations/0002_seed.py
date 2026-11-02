from django.db import migrations

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


class Migration(migrations.Migration):
    dependencies = [
        ("software_identity", "0001_initial"),
        ("scheduler", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
