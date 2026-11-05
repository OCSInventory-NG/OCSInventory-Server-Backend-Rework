from django.db import migrations


def drop_versions_inside_ranges(apps, schema_editor):
    """
    The affected versions enumerated from ECOSYSTEM ranges are no longer
    stored: they all lie inside the ranges (Debian and Ubuntu archives) and
    made 95% of the Ubuntu data.
    """
    OsvAffected = apps.get_model("security", "OsvAffected")
    OsvAffected.objects.exclude(ranges=[]).exclude(versions=[]).update(versions=[])


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0002_seed"),
    ]

    operations = [
        migrations.RunPython(drop_versions_inside_ranges, migrations.RunPython.noop),
    ]
