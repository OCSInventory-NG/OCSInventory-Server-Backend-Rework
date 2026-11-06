from django.db import migrations

# Debian urgencies no longer reported (security.evaluation.MINOR_RATINGS)
MINOR_RATINGS = ("unimportant", "not yet assigned")


def drop_minor_urgencies(apps, schema_editor):
    """
    The evaluations no longer keep the findings of a minor Debian urgency:
    their stored findings and exposures go, as a new evaluation would leave.
    """
    Finding = apps.get_model("security", "Finding")
    Exposure = apps.get_model("security", "Exposure")
    Finding.objects.filter(rating__in=MINOR_RATINGS).delete()
    Exposure.objects.filter(rating__in=MINOR_RATINGS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0005_source_data_changed_full_scan_task"),
    ]

    operations = [
        migrations.RunPython(drop_minor_urgencies, migrations.RunPython.noop),
    ]
