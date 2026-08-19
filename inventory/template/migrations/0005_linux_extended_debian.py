from django.db import migrations


def create_linux_extended_debian_template(apps, schema_editor):
    Template = apps.get_model("template", "Template")

    try:
        Template.objects.create(
            name="Linux Extended (Debian based)",
            os="DEB",
            is_protected=True,
        )
    except Exception as e:
        print(e)


class Migration(migrations.Migration):
    dependencies = [
        ("template", "0004_windows_extended"),
        ("field", "0011_windows_extended"),
    ]

    operations = [
        migrations.RunPython(create_linux_extended_debian_template),
    ]
