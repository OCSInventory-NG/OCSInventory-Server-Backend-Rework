from django.db import migrations

# Fragments of the default SOFTWARES commands changed here, as (current, new)
DEBIAN_SOFTWARES = [
    (r'major="";minor=""}', r'major="";minor="";source=""}'),
    (
        r" END {size=size_kb*1024;",
        r' /^Source[[:space:]]*:/ {source=substr($0,index($0,":")+2); sub(/ .*/, "", source)}'  # noqa: E501
        r' END {size=size_kb*1024; if(source==""){source=name; sub(/:.*/, "", source)}',
    ),
    (r'printf("---\n") }', r'printf("Source: %s\n", source); printf("---\n") }'),
]

RHEL_SOFTWARES = [
    (
        r" /^Summary/",
        r' /^Epoch/ {epoch=substr($0,index($0,":")+2)}'
        r' /^Source RPM/ {source=substr($0,index($0,":")+2); sub(/-[^-]+-[^-]+\.src\.rpm$/, "", source)}'  # noqa: E501
        r" /^Summary/",
    ),
    (
        r'END {split(version,vparts,".");',
        r'END {if(epoch!="" && epoch!="(none)") full_version=epoch":"full_version;'
        r' if(source=="" || source=="(none)") source=name;'
        r' split(version,vparts,".");',
    ),
    (r'Patch: %s\n---\n", name,', r'Patch: %s\nSource: %s\n---\n", name,'),
    (r"major, minor, patch}", r"major, minor, patch, source}"),
]

# VersionMajor/VersionMinor are registry values written by each installer
# (Edge writes 4191/53): derive them from DisplayVersion like VersionPatch.
# New names because "-Property *" already selects the registry values.
WINDOWS_SOFTWARES = [
    (
        r" -ExcludeProperty PSProvider, PSDrive",
        r", @{Name='DisplayVersionMajor';Expression={ if ($_.DisplayVersion) {"
        r" [regex]::Match((($_.DisplayVersion -split '\.')[0]), '^\d+').Value } else { $null } }},"  # noqa: E501
        r" @{Name='DisplayVersionMinor';Expression={ if ($_.DisplayVersion) {"
        r" [regex]::Match((($_.DisplayVersion -split '\.')[1]), '^\d+').Value } else { $null } }}"  # noqa: E501
        r" -ExcludeProperty PSProvider, PSDrive",
    ),
]

SOFTWARES_CHANGES = {
    ("Linux (Debian based)", "DEB"): DEBIAN_SOFTWARES,
    ("Linux (RHEL based)", "RHEL"): RHEL_SOFTWARES,
    ("Windows", "WIN"): WINDOWS_SOFTWARES,
}

OS_RELEASE_TARGET = (
    r"( . /etc/os-release; printf 'ID=%s\nID_LIKE=%s\nVERSION_ID=%s\nCODENAME=%s\n'"
    r' "$ID" "$ID_LIKE" "$VERSION_ID" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" );'
    r" printf 'RUNNING_KERNEL=%s\n' "
    r'"$(uname -r)"'
)

OS_RELEASE_SECTION = {
    "name": "OS RELEASE",
    "retrieval_method": "BASH",
    "retrieval_output": "REGX",
    "target": OS_RELEASE_TARGET,
    "options": {"multiple": False, "separator": None},
}

NEW_SECTIONS = {
    ("Linux (Debian based)", "DEB"): OS_RELEASE_SECTION,
    ("Linux (RHEL based)", "RHEL"): OS_RELEASE_SECTION,
    ("Windows", "WIN"): {
        "name": "OPERATING SYSTEM",
        "retrieval_method": "PW",
        "retrieval_output": "JSON",
        "target": (
            "Get-CimInstance Win32_OperatingSystem"
            " | Select-Object Caption, Version | ConvertTo-Json"
        ),
        "options": {"submap": None},
    },
    ("MacOS", "MAC"): {
        "name": "OPERATING SYSTEM",
        "retrieval_method": "BASH",
        "retrieval_output": "REGX",
        "target": "sw_vers",
        "options": {"multiple": False, "separator": None},
    },
}


def patch_command(target, changes):
    for current, new in changes:
        if target.count(current) != 1:
            raise ValueError(
                f"Default template command fragment not found once: {current}"
            )
        target = target.replace(current, new)
    return target


def reverse_changes(changes):
    return [(new, current) for current, new in reversed(changes)]


def _touch_templates(Template):
    # Agents download a template again when its last_update changes
    for name, os_type in set(SOFTWARES_CHANGES) | set(NEW_SECTIONS):
        Template.objects.get(name=name, os=os_type).save()


def add_identity_sections(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")

    for (name, os_type), changes in SOFTWARES_CHANGES.items():
        section = Section.objects.get(
            name="SOFTWARES", template__name=name, template__os=os_type
        )
        section.target = patch_command(section.target, changes)
        section.save()

    for (name, os_type), data in NEW_SECTIONS.items():
        Section.objects.create(
            template=Template.objects.get(name=name, os=os_type), **data
        )

    _touch_templates(Template)


def remove_identity_sections(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")

    for (name, os_type), data in NEW_SECTIONS.items():
        Section.objects.filter(
            name=data["name"], template__name=name, template__os=os_type
        ).delete()

    for (name, os_type), changes in SOFTWARES_CHANGES.items():
        section = Section.objects.get(
            name="SOFTWARES", template__name=name, template__os=os_type
        )
        section.target = patch_command(section.target, reverse_changes(changes))
        section.save()

    _touch_templates(Template)


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0014_section_is_active"),
    ]

    operations = [
        migrations.RunPython(
            add_identity_sections, reverse_code=remove_identity_sections
        ),
    ]
