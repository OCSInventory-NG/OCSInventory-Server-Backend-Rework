from django.db import migrations


def create_connected_user_fields(apps, schema_editor):
    Field = apps.get_model("field", "Field")
    Section = apps.get_model("section", "Section")

    sections = Section.objects.filter(
        name="CONNECTED USER", template__is_protected=True
    ).select_related("template")

    for section in sections:
        Field.objects.create(
            name="USER NAME",
            order=1,
            retrieval_value="UserName" if section.template.os == "WIN" else r"(\S+)",
            override_target=False,
            new_target=None,
            retrieval_method=None,
            retrieval_output=None,
            options=None,
            section=section,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0016_connected_user"),
        ("field", "0014_containers"),
    ]

    operations = [
        migrations.RunPython(create_connected_user_fields),
    ]
