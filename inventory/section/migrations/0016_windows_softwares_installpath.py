from django.db import migrations

SOFTWARES_TARGET = r"""Get-ItemProperty HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*, HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* | Where-Object { $_.DisplayName -and $_.SystemComponent -ne 1 } | Select-Object -Property * -ExcludeProperty LanguageName, InstallDateFormatted, InstallPath, ExecutableName, VersionPatch | Select-Object -Property *, @{Name='LanguageName';Expression={ try { if ($_.Language) { $lcid=[int]$_.Language; (New-Object System.Globalization.CultureInfo $lcid).DisplayName } else { 'Unknown' } } catch { 'Unknown' } }}, @{Name='InstallDateFormatted';Expression={ if ($_.InstallDate -match '^\d{8}$') { [datetime]::ParseExact($_.InstallDate,'yyyyMMdd',$null).ToString('yyyy/MM/dd') } else { 'Unknown' } }}, @{Name='InstallPath';Expression={ $exe=$null; $c=@($_.DisplayIcon,$_.UninstallString,$_.QuietUninstallString,$_.ModifyPath) | Where-Object { $_ -and $_.ToString().Trim() -ne '' }; foreach($s in $c){ $m=[regex]::Match($s,'(?i)(?:^|[ \t])"?(?<exe>(?:[a-z]:|\\)[^",]+?\.exe)'); if($m.Success){ $p=$m.Groups['exe'].Value.Trim('"'); $n=[System.IO.Path]::GetFileName($p); if($n -ieq 'msiexec.exe' -or $n -ieq 'rundll32.exe'){ continue }; $exe=$p; break } }; if ($_.InstallLocation) { $_.InstallLocation } elseif ($exe) { [System.IO.Path]::GetDirectoryName($exe) } else { $null } }}, @{Name='ExecutableName';Expression={ $exe=$null; $c=@($_.DisplayIcon,$_.UninstallString,$_.QuietUninstallString,$_.ModifyPath) | Where-Object { $_ -and $_.ToString().Trim() -ne '' }; foreach($s in $c){ $m=[regex]::Match($s,'(?i)(?:^|[ \t])"?(?<exe>(?:[a-z]:|\\)[^",]+?\.exe)'); if($m.Success){ $p=$m.Groups['exe'].Value.Trim('"'); $n=[System.IO.Path]::GetFileName($p); if($n -ieq 'msiexec.exe' -or $n -ieq 'rundll32.exe'){ continue }; $exe=$p; break } }; if($exe){ [System.IO.Path]::GetFileName($exe) } else { $null } }}, @{Name='VersionPatch';Expression={ if ($_.DisplayVersion) { [regex]::Match((($_.DisplayVersion -split '\.')[2]), '^\d+').Value } else { $null } }} -ExcludeProperty PSProvider, PSDrive | ConvertTo-Json -Depth 4"""


def update_windows_softwares_target(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Section = apps.get_model("section", "Section")

    # customised templates are duplicates, only the shipped ones are overwritten
    templates = Template.objects.filter(
        name__in=["Windows", "Windows Extended"], os="WIN", is_protected=True
    )

    for template in templates:
        Section.objects.filter(template=template, name="SOFTWARES").update(
            target=SOFTWARES_TARGET
        )
        # agents compare last_update to download the new template
        template.save()


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0015_containers"),
    ]

    operations = [
        migrations.RunPython(update_windows_softwares_target),
    ]
