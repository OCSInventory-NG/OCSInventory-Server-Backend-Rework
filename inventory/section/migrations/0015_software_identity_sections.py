from django.db import migrations

# Software identity: the default templates collect the source package (name,
# version, epoch), the package origin and the platform (os-release, uname -r;
# OS name and version on Windows and macOS). The SOFTWARES commands are patched
# fragment by fragment, as (current, new), in order: each list applies to the
# command as the lists before it left it.

# Source package name, with the RPM epoch
DEBIAN_SOURCE = [
    (r'major="";minor=""}', r'major="";minor="";source=""}'),
    (
        r" END {size=size_kb*1024;",
        r' /^Source[[:space:]]*:/ {source=substr($0,index($0,":")+2); sub(/ .*/, "", source)}'  # noqa: E501
        r' END {size=size_kb*1024; if(source==""){source=name; sub(/:.*/, "", source)}',
    ),
    (r'printf("---\n") }', r'printf("Source: %s\n", source); printf("---\n") }'),
]

RHEL_SOURCE = [
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

# Origin of every installed package, computed once before the package loop:
# the first repository of its installed version, else of its candidate
# version (the installed one is in no repository any more), else of the
# newest version listed when it is not the installed one (an Ubuntu phased
# update held back keeps the installed version as candidate), else empty.
# A repository's origin is the o= of its release line, else its host.
# Version lines may end with "(phased N%)". LC_ALL=C because apt translates
# its output.
ORIGINS = (
    r"""pkgs=$(dpkg -l | awk 'NR>5 {print $2}');"""
    r""" origins=$( { LC_ALL=C apt-cache policy; echo @@; LC_ALL=C apt-cache policy $pkgs; } 2>/dev/null | awk '"""  # noqa: E501
    r"""function flush() { if (name != "") print name "\t" (io != "" ? io : (co != "" ? co : no)) }"""  # noqa: E501
    r""" $0 == "@@" { part = 2; next }"""
    r""" part != 2 { if (match($0, /^ *-?[0-9]+ /)) { src = ""; if ($NF == "Packages") { src = substr($0, RLENGTH + 1); sub(/ Packages$/, "", src) } }"""  # noqa: E501
    r""" else if ($1 == "release" && src != "") { n = split(substr($0, index($0, "release ") + 8), kv, ","); for (i = 1; i <= n; i++) if (kv[i] ~ /^o=/) org[src] = substr(kv[i], 3) }"""  # noqa: E501
    r""" else if ($1 == "origin" && src != "" && org[src] == "") org[src] = $2; next }"""
    r""" /^[^ ].*:$/ { flush(); name = substr($0, 1, length($0) - 1); inst = ""; cand = ""; io = ""; co = ""; no = ""; ver = ""; nv = 0; next }"""  # noqa: E501
    r""" $1 == "Installed:" { inst = $2; next }"""
    r""" $1 == "Candidate:" { cand = $2; next }"""
    r""" $NF == "Packages" && match($0, /^ *-?[0-9]+ /) { s = substr($0, RLENGTH + 1); sub(/ Packages$/, "", s); if (ver == inst && io == "") io = org[s]; if (ver == cand && co == "") co = org[s]; if (nv == 1 && ver != inst && no == "") no = org[s]; next }"""  # noqa: E501
    r""" $1 == "***" { ver = $2; nv++; next }"""
    r""" $2 ~ /^-?[0-9]+$/ { ver = $1; nv++; next }"""
    r""" END { flush() }');"""
)
# One pass joins the package list with the origins, the loop reads both.
# apt drops the native architecture from names: "libc6:amd64" is "libc6".
JOIN = r""" { printf '%s\n' "$origins"; echo @@; printf '%s\n' "$pkgs"; } | awk -F '\t' '$0 == "@@" { p = 1; next } !p { org[$1] = $2; next } { b = $1; sub(/:[^:]*$/, "", b); print $1 "\t" (($1 in org) ? org[$1] : ((b in org) ? org[b] : "")) }' | while IFS="$(printf '\t')" read -r pkg origin; do"""  # noqa: E501
LOOP = r"""dpkg -l | awk 'NR>5 {print $2}' | while read -r pkg; do"""

# The package origin (apt), joined to the package loop
DEBIAN_ORIGIN = [
    (LOOP + " install_date=", ORIGINS + JOIN + " install_date="),
    (
        r"""-v id="$install_date" 'BEGIN""",
        r"""-v id="$install_date" -v origin="$origin" 'BEGIN""",
    ),
    (
        r'if(patch!="") printf("Patch: %s\n", patch);',
        r'if(patch!="") printf("Patch: %s\n", patch); printf("Origin: %s\n", origin);',
    ),
]

# The version of the source package, next to its name. Debian: the version in
# parentheses of the Source line ("samba (2:4.22.11+dfsg-1)"), else the
# package's own version. RHEL: the version-release of the Source RPM, with the
# package's epoch.
DEBIAN_SOURCE_VERSION = [
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

RHEL_SOURCE_VERSION = [
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
    ("Linux (Debian based)", "DEB"): DEBIAN_SOURCE
    + DEBIAN_ORIGIN
    + DEBIAN_SOURCE_VERSION,
    ("Linux (RHEL based)", "RHEL"): RHEL_SOURCE + RHEL_SOURCE_VERSION,
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
