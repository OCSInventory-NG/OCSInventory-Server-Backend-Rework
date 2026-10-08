from django.db import migrations

TEMPLATE = ("Linux (Debian based)", "DEB")
# Anchored on a line start: the agent compiles regexes without multiline mode
ORIGIN_FIELD = ("ORIGIN", r"(?:^|\n)Origin:[ \t]*(.*)")


def _softwares(Section):
    name, os_type = TEMPLATE
    return Section.objects.get(
        name="SOFTWARES", template__name=name, template__os=os_type
    )


def _touch_template(Template):
    # Agents download a template again when its last_update changes
    name, os_type = TEMPLATE
    Template.objects.get(name=name, os=os_type).save()


def add_origin_field(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    Field = apps.get_model("field", "Field")

    section = _softwares(Section)
    order = (
        Field.objects.filter(section=section)
        .order_by("-order")
        .values_list("order", flat=True)
        .first()
        or 0
    )
    name, retrieval_value = ORIGIN_FIELD
    Field.objects.create(
        name=name,
        retrieval_value=retrieval_value,
        override_target=False,
        new_target=None,
        retrieval_method=None,
        retrieval_output=None,
        options={},
        section=section,
        order=order + 1,
    )
    _touch_template(Template)


def remove_origin_field(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    Field = apps.get_model("field", "Field")

    Field.objects.filter(section=_softwares(Section), name=ORIGIN_FIELD[0]).delete()
    _touch_template(Template)


class Migration(migrations.Migration):
    dependencies = [
        ("field", "0014_software_identity_fields"),
        ("section", "0016_package_origin"),
    ]

    operations = [
        migrations.RunPython(add_origin_field, reverse_code=remove_origin_field),
    ]
