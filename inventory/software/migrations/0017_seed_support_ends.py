import datetime

from django.db import migrations

# (base, version, codename, end of standard support). Ubuntu LTS dates as
# published by Canonical; interim releases have no Ubuntu Pro.
RELEASES = [
    ("debian", "10", "buster", None),
    ("ubuntu", "16.04", "xenial", datetime.date(2021, 4, 30)),
    ("ubuntu", "18.04", "bionic", datetime.date(2023, 5, 31)),
    ("ubuntu", "20.04", "focal", datetime.date(2025, 5, 31)),
    ("ubuntu", "22.04", "jammy", datetime.date(2027, 6, 1)),
    ("ubuntu", "24.04", "noble", datetime.date(2029, 6, 1)),
    ("ubuntu", "24.10", "oracular", datetime.date(2025, 7, 10)),
    ("ubuntu", "25.04", "plucky", datetime.date(2026, 1, 15)),
    ("ubuntu", "25.10", "questing", datetime.date(2026, 7, 1)),
]
ADDED = ("buster", "xenial", "bionic", "oracular", "plucky", "questing")


def seed(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    for base, version, codename, end in RELEASES:
        DistroRelease.objects.update_or_create(
            base=base,
            codename=codename,
            defaults={"version": version, "standard_support_end": end},
        )


def unseed(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    DistroRelease.objects.filter(codename__in=ADDED).delete()
    DistroRelease.objects.update(standard_support_end=None)


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0016_distrorelease_support_end"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
