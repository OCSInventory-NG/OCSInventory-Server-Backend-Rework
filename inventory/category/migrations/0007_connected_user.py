from django.db import migrations


def add_connected_user_sections_to_category(apps, schema_editor):
    Section = apps.get_model("section", "Section")
    Category = apps.get_model("category", "Category")

    sections = Section.objects.filter(
        name="CONNECTED USER", template__is_protected=True
    )
    category = Category.objects.filter(name="Administrative data").first()
    if category:
        category.inventory_sections.add(*sections)


class Migration(migrations.Migration):
    dependencies = [
        ("category", "0006_containers"),
        ("section", "0016_connected_user"),
    ]

    operations = [
        migrations.RunPython(add_connected_user_sections_to_category),
    ]
