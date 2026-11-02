from django.db import migrations

TEMPLATES = (("Linux (Debian based)", "DEB"), ("Linux (RHEL based)", "RHEL"))
# Anchored on a line start: the agent compiles regexes without multiline mode
SOURCE_VERSION_FIELD = ("SOURCE VERSION", r"(?:^|\n)SourceVersion:[ \t]*(.*)")


def _softwares(Section, name, os_type):
    return Section.objects.get(
        name="SOFTWARES", template__name=name, template__os=os_type
    )


def add_source_version_field(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    Field = apps.get_model("field", "Field")

    field_name, retrieval_value = SOURCE_VERSION_FIELD
    for name, os_type in TEMPLATES:
        section = _softwares(Section, name, os_type)
        order = (
            Field.objects.filter(section=section)
            .order_by("-order")
            .values_list("order", flat=True)
            .first()
            or 0
        )
        Field.objects.create(
            name=field_name,
            retrieval_value=retrieval_value,
            override_target=False,
            new_target=None,
            retrieval_method=None,
            retrieval_output=None,
            options={},
            section=section,
            order=order + 1,
        )
        # Agents download a template again when its last_update changes
        Template.objects.get(name=name, os=os_type).save()


def remove_source_version_field(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    Field = apps.get_model("field", "Field")

    for name, os_type in TEMPLATES:
        Field.objects.filter(
            section=_softwares(Section, name, os_type),
            name=SOURCE_VERSION_FIELD[0],
        ).delete()
        Template.objects.get(name=name, os=os_type).save()


class Migration(migrations.Migration):
    dependencies = [
        ("field", "0015_package_origin_field"),
        ("section", "0017_source_version"),
    ]

    operations = [
        migrations.RunPython(
            add_source_version_field, reverse_code=remove_source_version_field
        ),
    ]
