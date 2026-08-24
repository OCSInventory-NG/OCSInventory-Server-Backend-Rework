from django.db import migrations


def add_linux_extended_debian_sections_to_categories(apps, schema_editor):
    Section = apps.get_model("section", "Section")
    Category = apps.get_model("category", "Category")
    Template = apps.get_model("template", "Template")

    template = Template.objects.get(name="Linux Extended (Debian based)", os="DEB")
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
            "REPOSITORY",
            "VIRTUAL MACHINES",
            "TEAM VIEWER",
            "FIREWALL RULES",
            "UPTIME",
            "SECURITY CERTIFICATE",
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
        ("category", "0003_windows_extended"),
        ("section", "0012_linux_extended_debian"),
    ]

    operations = [
        migrations.RunPython(add_linux_extended_debian_sections_to_categories),
    ]
