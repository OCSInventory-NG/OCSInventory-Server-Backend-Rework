from django.db import migrations

# Origins whose packages their distribution's advisories cover. Left out on
# purpose: "Fedora Project" (on a RHEL rebuild it means EPEL; a Fedora fleet
# adds the row), LinuxMint, Pop!_OS, Docker, Google...: third party.
PACKAGE_ORIGINS = [
    ("Debian", "debian"),
    ("Ubuntu", "ubuntu"),
    ("Rocky Enterprise Software Foundation", "rocky"),
    ("AlmaLinux", "almalinux"),
    ("Red Hat, Inc.", "redhat"),
    ("CentOS", "centos"),
]


def seed_package_origins(apps, schema_editor):
    PackageOrigin = apps.get_model("software_identity", "PackageOrigin")
    PackageOrigin.objects.bulk_create(
        [
            PackageOrigin(name=name, distribution=distribution)
            for name, distribution in PACKAGE_ORIGINS
        ]
    )


def unseed_package_origins(apps, schema_editor):
    PackageOrigin = apps.get_model("software_identity", "PackageOrigin")
    PackageOrigin.objects.filter(
        name__in=[name for name, _ in PACKAGE_ORIGINS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("software_identity", "0004_packageorigin"),
    ]

    operations = [
        migrations.RunPython(
            seed_package_origins, reverse_code=unseed_package_origins
        ),
    ]
