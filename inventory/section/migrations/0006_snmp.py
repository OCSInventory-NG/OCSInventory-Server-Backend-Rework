from django.db import migrations


def create_snmp_sections(apps, schema_editor):
    Section = apps.get_model("section", "Section")
    Template = apps.get_model("template", "Template")

    template = Template.objects.get(os="SNMP")

    sections = [
        {
            "name": "SYSTEM",
            "retrieval_method": "SNMP_GET",
            "retrieval_output": "JSON",
            "target": "SNMP",
            "template": template,
            "options": {"need_format": False},
        },
        {
            "name": "INTERFACES",
            "retrieval_method": "SNMP_WALK",
            "retrieval_output": "JSON",
            "target": "SNMP",
            "template": template,
            "options": {"need_format": False},
        },
        {
            "name": "IP",
            "retrieval_method": "SNMP_WALK",
            "retrieval_output": "JSON",
            "target": "SNMP",
            "template": template,
            "options": {"need_format": False},
        },
        {
            "name": "HARDWARE",
            "retrieval_method": "SNMP_WALK",
            "retrieval_output": "JSON",
            "target": "SNMP",
            "template": template,
            "options": {"need_format": False},
        },
    ]

    for section in sections:
        Section.objects.create(**section)


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0005_windows"),
    ]

    operations = [
        migrations.RunPython(create_snmp_sections),
    ]
