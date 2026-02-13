from django.db import migrations


def create_default_legacy_software_mapping(apps, schema_editor):
    Template = apps.get_model("template", "Template").objects.get(os="LEG")
    Section = apps.get_model("section", "Section").objects.get(
        name="SOFTWARES",
        template=Template,
    )
    
    software_mapping = {
        "template": Template,
        "section": Section,
        "name": apps.get_model("field", "Field").objects.get(
            name="NAME",
            section=Section,
        ),
        "publisher": apps.get_model("field", "Field").objects.get(
            name="PUBLISHER",
            section=Section,
        ),
        "version": apps.get_model("field", "Field").objects.get(
            name="VERSION",
            section=Section,
        ),
    }
    
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")
    
    try:
        SoftwareMapping.objects.create(**software_mapping)
    except Exception as e:
        print(e)


class Migration(migrations.Migration):
    
    dependencies = [
        ("software", "0005_debian_linux"),
    ]
    
    operations = [
        migrations.RunPython(create_default_legacy_software_mapping),
    ]