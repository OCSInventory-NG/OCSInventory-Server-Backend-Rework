from django.db import migrations

RELEASES = [
    ("debian", "11", "bullseye"),
    ("debian", "12", "bookworm"),
    ("debian", "13", "trixie"),
    ("ubuntu", "20.04", "focal"),
    ("ubuntu", "22.04", "jammy"),
    ("ubuntu", "24.04", "noble"),
]


def seed_distro_releases(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    DistroRelease.objects.bulk_create(
        [
            DistroRelease(base=base, version=version, codename=codename)
            for base, version, codename in RELEASES
        ]
    )


def unseed_distro_releases(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    DistroRelease.objects.filter(
        codename__in=[codename for _, _, codename in RELEASES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0008_distrorelease"),
    ]

    operations = [
        migrations.RunPython(seed_distro_releases, reverse_code=unseed_distro_releases),
    ]
