from django.db import migrations


def add_windows_extended_sections_to_categories(apps, schema_editor):
    Section = apps.get_model("section", "Section")
    Category = apps.get_model("category", "Category")
    Template = apps.get_model("template", "Template")

    template = Template.objects.get(name="Windows Extended", os="WIN")
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
            "DEFAULT WINDOWS APP",
            "WIN SERVER FEATURES",
            "FIREWALL RULES",
            "UPTIME",
            "OS INSTALL",
            "POWERSHELL VERSION",
            "DRIVERS LIST",
            "SCHEDULED TASKS",
            "SECURITY CERTIFICATE",
            "SERVICES",
            "WIN SEC DETAILS",
            "WMI PRODUCT LIST",
            "ANY DESK",
            "USER INSTALLED APPS",
            "FIREWALL CONFIG",
            "WIN UPDATE",
            "UNIVERSAL WINDOWS PLATFORMS APPS",
            "TEAM VIEWER",
            "BROWSERS EXTENSIONS",
            "BITLOCKER STATUS",
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
        ("category", "0002_legacy_extended"),
        ("section", "0011_windows_extended"),
    ]

    operations = [
        migrations.RunPython(add_windows_extended_sections_to_categories),
    ]
