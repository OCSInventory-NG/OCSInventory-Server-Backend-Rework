import datetime

from django.db import migrations, models

# (base, version): end of every security support. Debian: end of its LTS.
# Ubuntu LTS: end of Ubuntu Pro (ESM), the Legacy add-on left out; interim
# releases: their end of life.
SUPPORT_ENDS = {
    ("debian", "10"): datetime.date(2024, 6, 30),
    ("debian", "11"): datetime.date(2026, 8, 31),
    ("debian", "12"): datetime.date(2028, 6, 30),
    ("debian", "13"): datetime.date(2030, 6, 30),
    ("ubuntu", "16.04"): datetime.date(2026, 4, 30),
    ("ubuntu", "18.04"): datetime.date(2028, 5, 31),
    ("ubuntu", "20.04"): datetime.date(2030, 5, 31),
    ("ubuntu", "22.04"): datetime.date(2032, 6, 1),
    ("ubuntu", "24.04"): datetime.date(2034, 6, 1),
    ("ubuntu", "24.10"): datetime.date(2025, 7, 10),
    ("ubuntu", "25.04"): datetime.date(2026, 1, 15),
    ("ubuntu", "25.10"): datetime.date(2026, 7, 1),
}


def seed(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    for (base, version), end in SUPPORT_ENDS.items():
        # A date an administrator already set stays
        DistroRelease.objects.filter(
            base=base, version=version, support_end__isnull=True
        ).update(support_end=end)


class Migration(migrations.Migration):

    dependencies = [
        ("software", "0010_dictionary_signature_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="distrorelease",
            name="support_end",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
