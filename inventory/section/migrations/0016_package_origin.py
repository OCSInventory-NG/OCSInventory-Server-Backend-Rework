from django.db import migrations

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
JOIN = (
    r""" { printf '%s\n' "$origins"; echo @@; printf '%s\n' "$pkgs"; } | awk -F '\t' '$0 == "@@" { p = 1; next } !p { org[$1] = $2; next } { b = $1; sub(/:[^:]*$/, "", b); print $1 "\t" (($1 in org) ? org[$1] : ((b in org) ? org[b] : "")) }' | while IFS="$(printf '\t')" read -r pkg origin; do"""  # noqa: E501
)
LOOP = r"""dpkg -l | awk 'NR>5 {print $2}' | while read -r pkg; do"""

# Fragments of the default Debian SOFTWARES command changed here, as
# (current, new). None of them overlaps a fragment of section 0015.
DEBIAN_SOFTWARES = [
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

TEMPLATE = ("Linux (Debian based)", "DEB")


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


def _patch_softwares(apps, changes):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")
    name, os_type = TEMPLATE
    section = Section.objects.get(
        name="SOFTWARES", template__name=name, template__os=os_type
    )
    section.target = patch_command(section.target, changes)
    section.save()
    # Agents download a template again when its last_update changes
    Template.objects.get(name=name, os=os_type).save()


def add_package_origin(apps, schema_editor):
    _patch_softwares(apps, DEBIAN_SOFTWARES)


def remove_package_origin(apps, schema_editor):
    _patch_softwares(apps, reverse_changes(DEBIAN_SOFTWARES))


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0015_software_identity_sections"),
    ]

    operations = [
        migrations.RunPython(add_package_origin, reverse_code=remove_package_origin),
    ]
