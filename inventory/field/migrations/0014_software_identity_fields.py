from django.db import migrations

SOURCE_FIELD = [("SOURCE", r"(?:^|\n)Source:[ \t]*(.*)")]
# Anchored on a line start: the agent compiles regexes without multiline mode
OS_RELEASE_FIELDS = [
    (name, rf"(?:^|\n){name}=(.*)")
    for name in ("ID", "ID_LIKE", "VERSION_ID", "CODENAME", "RUNNING_KERNEL")
]

NEW_FIELDS = {
    ("Linux (Debian based)", "DEB", "SOFTWARES"): SOURCE_FIELD,
    ("Linux (RHEL based)", "RHEL", "SOFTWARES"): SOURCE_FIELD,
    ("Linux (Debian based)", "DEB", "OS RELEASE"): OS_RELEASE_FIELDS,
    ("Linux (RHEL based)", "RHEL", "OS RELEASE"): OS_RELEASE_FIELDS,
    ("Windows", "WIN", "OPERATING SYSTEM"): [
        ("OS NAME", "Caption"),
        ("OS VERSION", "Version"),
    ],
    ("MacOS", "MAC", "OPERATING SYSTEM"): [
        ("OS NAME", r"(?:^|\n)ProductName:[ \t]*(.*)"),
        ("OS VERSION", r"(?:^|\n)ProductVersion:[ \t]*(.*)"),
    ],
}

# Field name: (registry value, calculated property of the SOFTWARES command)
WINDOWS_VERSION_FIELDS = {
    "MAJOR": ("VersionMajor", "DisplayVersionMajor"),
    "MINOR": ("VersionMinor", "DisplayVersionMinor"),
}


def _section(Section, template_name, os_type, section_name):
    return Section.objects.get(
        name=section_name, template__name=template_name, template__os=os_type
    )


def _set_windows_version_fields(Field, Section, index):
    section = _section(Section, "Windows", "WIN", "SOFTWARES")
    for name, values in WINDOWS_VERSION_FIELDS.items():
        Field.objects.filter(section=section, name=name).update(
            retrieval_value=values[index]
        )


def _touch_templates(Template):
    # Agents download a template again when its last_update changes
    for name, os_type in {(name, os_type) for name, os_type, _ in NEW_FIELDS}:
        Template.objects.get(name=name, os=os_type).save()


def add_identity_fields(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    Field = apps.get_model("field", "Field")

    for (template_name, os_type, section_name), fields in NEW_FIELDS.items():
        section = _section(Section, template_name, os_type, section_name)
        order = (
            Field.objects.filter(section=section).order_by("-order")
            .values_list("order", flat=True).first()
            or 0
        )
        for name, retrieval_value in fields:
            order += 1
            Field.objects.create(
                name=name,
                retrieval_value=retrieval_value,
                override_target=False,
                new_target=None,
                retrieval_method=None,
                retrieval_output=None,
                options={},
                section=section,
                order=order,
            )

    _set_windows_version_fields(Field, Section, 1)
    _touch_templates(Template)


def remove_identity_fields(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    Field = apps.get_model("field", "Field")

    for (template_name, os_type, section_name), fields in NEW_FIELDS.items():
        section = _section(Section, template_name, os_type, section_name)
        Field.objects.filter(
            section=section, name__in=[name for name, _ in fields]
        ).delete()

    _set_windows_version_fields(Field, Section, 0)
    _touch_templates(Template)


class Migration(migrations.Migration):
    dependencies = [
        ("field", "0013_linux_extended_rhel"),
        ("section", "0015_software_identity_sections"),
    ]

    operations = [
        migrations.RunPython(
            add_identity_fields, reverse_code=remove_identity_fields
        ),
    ]
