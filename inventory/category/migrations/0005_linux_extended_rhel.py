from django.db import migrations


def add_linux_extended_rhel_sections_to_categories(apps, schema_editor):
    Section = apps.get_model("section", "Section")
    Category = apps.get_model("category", "Category")
    Template = apps.get_model("template", "Template")

    template = Template.objects.get(name="Linux Extended (RHEL based)", os="RHEL")
    sections = Section.objects.filter(template=template)

    category_sections = {
        "Administrative data": [
            "LOCAL USERS",
            "LOCAL GROUPS",
        ],
        "Hardware": [
            "BATTERIES",
            "BIOS",
            "CONTROLLERS",
            "CPUS",
            "DRIVES",
            "MEMORIES",
            "PORTS",
            "SLOTS",
            "SOUNDS",
            "STORAGES",
            "VIDEOS",
        ],
        "Networks": [
            "NETWORKS",
        ],
        "Devices": [
            "MONITORS",
            "INPUTS",
            "USB DEVICES",
            "PRINTERS",
        ],
        "Softwares": [
            "SOFTWARES",
        ],
        "Others": [
            "VIRTUAL MACHINES",
            "REPOSITORY",
            "UPTIME",
            "SECURITY CERTIFICATE",
            "TEAM VIEWER",
            "FIREWALL RULES",
            "REDHAT ERRATA",
            "CRON TAB TASKS",
            "RUNNING PROCESS",
        ],
    }

    for category_name, section_names in category_sections.items():
        try:
            category = Category.objects.get(name=category_name)
        except Category.DoesNotExist as e:
            print(e)
            continue

        matching_sections = sections.filter(name__in=section_names)
        category.inventory_sections.add(*matching_sections)


class Migration(migrations.Migration):
    dependencies = [
        ("category", "0004_linux_extended_debian"),
        ("section", "0013_linux_extended_rhel"),
    ]

    operations = [
        migrations.RunPython(add_linux_extended_rhel_sections_to_categories),
    ]
