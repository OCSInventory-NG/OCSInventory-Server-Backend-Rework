from django.db import migrations


def add_containers_sections_to_categories(apps, schema_editor):
    Section = apps.get_model("section", "Section")
    Category = apps.get_model("category", "Category")
    Template = apps.get_model("template", "Template")

    templates = [
        Template.objects.get(name="Linux Extended (Debian based)", os="DEB"),
        Template.objects.get(name="Linux Extended (RHEL based)", os="RHEL"),
        Template.objects.get(name="Windows Extended", os="WIN"),
    ]
    sections = Section.objects.filter(template__in=templates)

    category_sections = {
        "Softwares": [
            "CONTAINER SOFTWARES",
        ],
        "Others": [
            "CONTAINERS",
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
        ("category", "0005_linux_extended_rhel"),
        ("section", "0015_containers"),
    ]

    operations = [
        migrations.RunPython(add_containers_sections_to_categories),
    ]
