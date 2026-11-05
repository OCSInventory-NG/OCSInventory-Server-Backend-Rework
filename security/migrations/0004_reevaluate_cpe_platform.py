from django.db import migrations


def reevaluate_cpe(apps, schema_editor):
    """
    The NVD matches now skip the CPEs of another operating system (target_sw):
    the Windows and macOS evaluations are made again by the next scan.
    """
    Evaluation = apps.get_model("security", "Evaluation")
    Evaluation.objects.filter(scheme="cpe").update(sources={})


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0003_osv_versions_inside_ranges"),
    ]

    operations = [
        migrations.RunPython(reevaluate_cpe, migrations.RunPython.noop),
    ]
