from django.db import migrations


def create_snmp_fields(apps, schema_editor):
    Field = apps.get_model("field", "Field")
    Section = apps.get_model("section", "Section")
    Template = apps.get_model("template", "Template")

    template = Template.objects.get(os="SNMP")

    fields = [
        # SYSTEM section fields
        {
            "name": "Location",
            "order": 1,
            "retrieval_value": "1.3.6.1.2.1.1.6.0",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="SYSTEM", template=template),
            "options": None,
        },
        {
            "name": "Contact",
            "order": 2,
            "retrieval_value": "1.3.6.1.2.1.1.4.0",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="SYSTEM", template=template),
            "options": None,
        },
        {
            "name": "Uptime",
            "order": 3,
            "retrieval_value": "1.3.6.1.2.1.1.3.0",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="SYSTEM", template=template),
            "options": None,
        },
        {
            "name": "Boot path",
            "order": 4,
            "retrieval_value": "1.3.6.1.2.1.25.1.4.0",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="SYSTEM", template=template),
            "options": None
        },
        # INTERFACES section fields
        {
            "name": "Interface Name",
            "order": 1,
            "retrieval_value": "1.3.6.1.2.1.2.2.1.2",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="INTERFACES", template=template),
            "options": None,
        },
        {
            "name": "MAC Address",
            "order": 2,
            "retrieval_value": "1.3.6.1.2.1.2.2.1.6",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="INTERFACES", template=template),
            "options": None,
        },
        {
            "name": "Speed",
            "order": 3,
            "retrieval_value": "1.3.6.1.2.1.2.2.1.5",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="INTERFACES", template=template),
            "options": None,
        },
        {
            "name": "Status",
            "order": 4,
            "retrieval_value": "1.3.6.1.2.1.2.2.1.8",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="INTERFACES", template=template),
            "options": None,
        },
        {
            "name": "InErrors",
            "order": 5,
            "retrieval_value": "1.3.6.1.2.1.2.2.1.14",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="INTERFACES", template=template),
            "options": None,
        },
        {
            "name": "OutErrors",
            "order": 6,
            "retrieval_value": "1.3.6.1.2.1.2.2.1.20",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="INTERFACES", template=template),
            "options": None,
        },
        # IP section fields
        {
            "name": "IP",
            "order": 1,
            "retrieval_value": "1.3.6.1.2.1.4.20.1.1",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="IP", template=template),
            "options": None,
        },
        {
            "name": "Netmask",
            "order": 2,
            "retrieval_value": "1.3.6.1.2.1.4.20.1.3",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="IP", template=template),
            "options": None,
        },
        # HARDWARE
        {
            "name": "Device name",
            "order": 1,
            "retrieval_value": "1.3.6.1.2.1.25.3.2.1.3",
            "override_target": False,
            "new_target": None,
            "retrieval_method": None,
            "retrieval_output": None,
            "section": Section.objects.get(name="HARDWARE", template=template),
            "options": None
        }
    ]

    for field in fields:
        Field.objects.create(**field)


class Migration(migrations.Migration):
    dependencies = [("section", "0006_snmp"), ("field", "0005_windows")]

    operations = [
        migrations.RunPython(create_snmp_fields),
    ]
