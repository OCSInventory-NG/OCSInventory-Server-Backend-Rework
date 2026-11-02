from django.db import migrations

# The version of the source package, next to its name. Debian: the version in
# parentheses of the Source line ("samba (2:4.22.11+dfsg-1)"), else the
# package's own version. RHEL: the version-release of the Source RPM, with the
# package's epoch. None of these fragments overlaps one of 0015 or 0016.
DEBIAN_SOFTWARES = [
    (r'minor="";source=""}', r'minor="";source="";srcver=""}'),
    (
        r'/^Source[[:space:]]*:/ {source=substr($0,index($0,":")+2); sub(/ .*/, "", source)}',  # noqa: E501
        r'/^Source[[:space:]]*:/ {source=substr($0,index($0,":")+2); if(match(source,/\(.*\)/)) srcver=substr(source,RSTART+1,RLENGTH-2); sub(/ .*/, "", source)}',  # noqa: E501
    ),
    (
        r'if(source==""){source=name; sub(/:.*/, "", source)}',
        r'if(source==""){source=name; sub(/:.*/, "", source)} if(srcver=="") srcver=version;',  # noqa: E501
    ),
    (
        r'printf("Source: %s\n", source);',
        r'printf("Source: %s\n", source); printf("SourceVersion: %s\n", srcver);',
    ),
]

RHEL_SOFTWARES = [
    (
        r'/^Source RPM/ {source=substr($0,index($0,":")+2); sub(/-[^-]+-[^-]+\.src\.rpm$/, "", source)}',  # noqa: E501
        r'/^Source RPM/ {source=substr($0,index($0,":")+2); srpm=source; sub(/-[^-]+-[^-]+\.src\.rpm$/, "", source); srcver=substr(srpm, length(source)+2); sub(/\.src\.rpm$/, "", srcver)}',  # noqa: E501
    ),
    (
        r'END {if(epoch!="" && epoch!="(none)") full_version=epoch":"full_version;',
        r'END {if(srcver=="" || source=="(none)") srcver=version"-"release;'
        r' if(epoch!="" && epoch!="(none)") {full_version=epoch":"full_version; srcver=epoch":"srcver}',  # noqa: E501
    ),
    (
        r'Patch: %s\nSource: %s\n---\n", name,',
        r'Patch: %s\nSource: %s\nSourceVersion: %s\n---\n", name,',
    ),
    (r"major, minor, patch, source}", r"major, minor, patch, source, srcver}"),
]

SOFTWARES_CHANGES = {
    ("Linux (Debian based)", "DEB"): DEBIAN_SOFTWARES,
    ("Linux (RHEL based)", "RHEL"): RHEL_SOFTWARES,
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


def _patch(apps, reverse):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    for (name, os_type), changes in SOFTWARES_CHANGES.items():
        section = Section.objects.get(
            name="SOFTWARES", template__name=name, template__os=os_type
        )
        section.target = patch_command(
            section.target, reverse_changes(changes) if reverse else changes
        )
        section.save()
        # Agents download a template again when its last_update changes
        Template.objects.get(name=name, os=os_type).save()


def add_source_version(apps, schema_editor):
    _patch(apps, reverse=False)


def remove_source_version(apps, schema_editor):
    _patch(apps, reverse=True)


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0016_package_origin"),
    ]

    operations = [
        migrations.RunPython(add_source_version, reverse_code=remove_source_version),
    ]
