from django.db import migrations


def add_legacy_extended_sections_to_categories(apps, schema_editor):
    Section = apps.get_model("section", "Section")
    Category = apps.get_model("category", "Category")
    Template = apps.get_model("template", "Template")

    template = Template.objects.get(name="Legacy Extended", os="LEG")
    sections = Section.objects.filter(template=template)

    category_sections = {
        "Administrative data": [
            "ACCOUNTINFO",
            "LOCAL_USERS",
            "LOCAL_GROUPS",
        ],
        "Hardware": [
            "BATTERIES",
            "BIOS",
            "CONTROLLERS",
            "CPUS",
            "DRIVES",
            "HARDWARE",
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
            "USBDEVICES",
            "PRINTERS",
            "MODEMS",
        ],
        "Softwares": [
            "SOFTWARES",
        ],
        "Others": [
            "VIRTUALMACHINES",
            "REPOSITORY",
            "ANYDESK",
            "DRIVERSLIST",
            "POWERSHELLVERSION",
            "TEAMVIEWER",
            "BITLOCKERSTATUS",
            "FIREWALLCONFIG",
            "SCHEDULEDTASKS",
            "BROWSEREXTENSIONS",
            "FIREWALLRULES",
            "SECURITYCERTIFICATE",
            "UWPAPPS",
            "USERINSTALLEDAPPS",
            "DEFAULTWINDOWSAPP",
            "OSINSTALL",
            "SERVICES",
            "UPTIME",
            "WINSECDETAILS",
            "WINSERVERFEATURES",
            "WINUPDATESTATE",
            "WINUPDATESCAN",
            "WMIPRODUCTLIST",
            "WINUSERS",
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
        ("category", "0001_initial"),
        ("section", "0010_legacy_extended"),
    ]

    operations = [
        migrations.RunPython(add_legacy_extended_sections_to_categories),
    ]
