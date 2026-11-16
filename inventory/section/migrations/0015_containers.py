from django.db import migrations


def create_containers_sections(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")

    linux_sections = [
        {
            "name": "CONTAINERS",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'for rt in docker podman; do command -v $rt >/dev/null 2>&1 || continue; [ $rt = docker ] && docker --version 2>/dev/null | grep -qi podman && continue;ids=$($rt ps -aq 2>/dev/null); [ -n "$ids" ] && $rt inspect --format "Runtime: $rt{{println}}Name: {{.Name}}{{println}}Id: {{printf \\"%.12s\\" .ID}}{{println}}Image: {{.Config.Image}}{{println}}State: {{.State.Status}}{{println}}Created: {{.Created}}{{println}}Ports: {{range \\$p, \\$b := .NetworkSettings.Ports}}{{\\$p}}{{range \\$b}} {{.HostIP}}:{{.HostPort}}{{end}}; {{end}}{{println}}Mounts: {{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}{{println}}Compose project: {{index .Config.Labels \\"com.docker.compose.project\\"}}{{println}}Working dir: {{index .Config.Labels \\"com.docker.compose.project.working_dir\\"}}{{println}}Compose files: {{index .Config.Labels \\"com.docker.compose.project.config_files\\"}}{{println}}" $ids; done 2>/dev/null',
            "options": {"multiple": False, "separator": "Runtime:"},
            "is_active": True,
        },
        {
            "name": "CONTAINER SOFTWARES",
            "retrieval_method": "BASH",
            "retrieval_output": "REGX",
            "target": 'for rt in docker podman; do command -v $rt >/dev/null 2>&1 || continue; [ $rt = docker ] && docker --version 2>/dev/null | grep -qi podman && continue;for id in $($rt ps -q 2>/dev/null); do name=$($rt inspect --format \'{{.Name}}\' $id); $rt exec $id sh -c \'dpkg-query -W 2>/dev/null || rpm -qa --qf %{NAME}\\\\t%{VERSION}-%{RELEASE}\\\\n 2>/dev/null || apk info -v 2>/dev/null\' 2>/dev/null | sed \'/\\t/!s/^\\(.*\\)-\\([^-]*-r[0-9]*\\)$/\\1\\t\\2/\' | while IFS="$(printf \'\\t\')" read -r pkg ver; do printf "Container: %s\\nName: %s\\nVersion: %s\\n" "${name#/}" "$pkg" "$ver"; done; done; done',
            "options": {"multiple": False, "separator": "Container:"},
            # runs a command inside each running container: disabled by default
            "is_active": False,
        },
    ]

    windows_sections = [
        {
            "name": "CONTAINERS",
            "retrieval_method": "PW",
            "retrieval_output": "JSON",
            "target": "$r = foreach ($rt in 'docker', 'podman') { if (Get-Command $rt -ErrorAction SilentlyContinue) { $ids = & $rt ps -aq 2>$null; if ($ids) { (& $rt inspect $ids | Out-String | ConvertFrom-Json) | Select-Object @{Name='Runtime';Expression={$rt}}, @{Name='Name';Expression={$_.Name.TrimStart('/')}}, @{Name='Id';Expression={$_.Id.Substring(0,12)}}, @{Name='Image';Expression={$_.Config.Image -replace '(:[\\w][\\w.-]*)?(@\\S+)?$', ''}}, @{Name='Tag';Expression={if ($_.Config.Image -match ':([\\w][\\w.-]*)(@\\S+)?$') { $Matches[1] } else { '' }}}, @{Name='State';Expression={$_.State.Status}}, @{Name='Created';Expression={[string]$_.Created}}, @{Name='Ports';Expression={$o = foreach ($p in $_.NetworkSettings.Ports.PSObject.Properties) { foreach ($b in $p.Value) { \"$($p.Name) $($b.HostIp):$($b.HostPort)\" } }; $o -join '; '}}, @{Name='Mounts';Expression={$o = foreach ($m in $_.Mounts) { \"$($m.Source):$($m.Destination)\" }; $o -join ' '}}, @{Name='ComposeProject';Expression={$_.Config.Labels.'com.docker.compose.project'}}, @{Name='WorkingDir';Expression={$_.Config.Labels.'com.docker.compose.project.working_dir'}}, @{Name='ComposeFiles';Expression={$_.Config.Labels.'com.docker.compose.project.config_files'}} } } }; @($r) | ConvertTo-Json -Depth 3",
            "options": {"submap": None},
            "is_active": True,
        },
        {
            "name": "CONTAINER SOFTWARES",
            "retrieval_method": "PW",
            "retrieval_output": "JSON",
            "target": "$s = 'dpkg-query -W 2>/dev/null || rpm -qa --qf %{NAME}\\\\t%{VERSION}-%{RELEASE}\\\\n 2>/dev/null || apk info -v 2>/dev/null'; $r = foreach ($rt in 'docker', 'podman') { if (Get-Command $rt -ErrorAction SilentlyContinue) { foreach ($id in (& $rt ps -q 2>$null)) { $name = (& $rt inspect --format '{{.Name}}' $id).TrimStart('/'); foreach ($l in (& $rt exec $id sh -c $s 2>$null)) { if ($l -match '^(.+?)\\t(.*)$' -or $l -match '^(.*)-([^-]*-r\\d+)$') { [PSCustomObject]@{Container = $name; Name = $Matches[1]; Version = $Matches[2]} } elseif ($l) { [PSCustomObject]@{Container = $name; Name = $l; Version = ''} } } } } }; @($r) | ConvertTo-Json",
            "options": {"submap": None},
            # runs a command inside each running container: disabled by default
            "is_active": False,
        },
    ]

    templates_sections = [
        (
            Template.objects.get(name="Linux Extended (Debian based)", os="DEB"),
            linux_sections,
        ),
        (
            Template.objects.get(name="Linux Extended (RHEL based)", os="RHEL"),
            linux_sections,
        ),
        (Template.objects.get(name="Windows Extended", os="WIN"), windows_sections),
    ]

    for template, sections in templates_sections:
        for section in sections:
            try:
                Section.objects.create(template=template, **section)
            except Exception as e:
                print(e)

        # historical models don't trigger the post_save signal updating
        # last_update, which agents compare to download the new template
        template.save()


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0014_section_is_active"),
        ("template", "0006_linux_extended_rhel"),
    ]

    operations = [
        migrations.RunPython(create_containers_sections),
    ]
