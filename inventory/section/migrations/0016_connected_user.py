from django.db import migrations

UNIX_SECTION = {
    "name": "CONNECTED USER",
    "retrieval_method": "BASH",
    "retrieval_output": "REGX",
    "target": "who | awk '{print $1}' | sort -u",
    "options": {"multiple": True, "separator": None},
    "is_active": True,
}

WINDOWS_SECTION = {
    "name": "CONNECTED USER",
    "retrieval_method": "PW",
    "retrieval_output": "JSON",
    "target": r"""$users = @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'explorer.exe'" -ErrorAction SilentlyContinue | ForEach-Object { $owner = Invoke-CimMethod -InputObject $_ -MethodName GetOwner -ErrorAction SilentlyContinue; if ($owner.User) { "$($owner.Domain)\$($owner.User)" } } | Sort-Object -Unique | ForEach-Object { [PSCustomObject]@{UserName = $_} }); if ($users) { $users | ConvertTo-Json } else { '[]' }""",
    "options": {"submap": None},
    "is_active": True,
}

TEMPLATES_SECTION = [
    ("Windows", "WIN", WINDOWS_SECTION),
    ("Windows Extended", "WIN", WINDOWS_SECTION),
    ("MacOS", "MAC", UNIX_SECTION),
    ("Linux (Debian based)", "DEB", UNIX_SECTION),
    ("Linux (RHEL based)", "RHEL", UNIX_SECTION),
    ("Linux Extended (Debian based)", "DEB", UNIX_SECTION),
    ("Linux Extended (RHEL based)", "RHEL", UNIX_SECTION),
]


def create_connected_user_sections(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")

    for name, os, section in TEMPLATES_SECTION:
        # customised templates are duplicates, only the shipped ones get the section
        for template in Template.objects.filter(name=name, os=os, is_protected=True):
            Section.objects.create(template=template, **section)
            # agents compare last_update to download the new template
            template.save()


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0015_containers"),
        ("template", "0006_linux_extended_rhel"),
    ]

    operations = [
        migrations.RunPython(create_connected_user_sections),
    ]
