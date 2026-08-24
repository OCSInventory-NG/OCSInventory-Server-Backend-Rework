from django.db import migrations


def create_linux_extended_rhel_template(apps, schema_editor):
    Template = apps.get_model("template", "Template")

    try:
        Template.objects.create(
            name="Linux Extended (RHEL based)",
            os="RHEL",
            is_protected=True,
        )
    except Exception as e:
        print(e)


class Migration(migrations.Migration):
    dependencies = [
        ("template", "0005_linux_extended_debian"),
        ("field", "0012_linux_extended_debian"),
    ]

    operations = [
        migrations.RunPython(create_linux_extended_rhel_template),
    ]
