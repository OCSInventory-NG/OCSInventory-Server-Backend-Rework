import django.db.models.deletion
from django.db import migrations, models

INITIAL_MAPPINGS = [
    (19044, "21h2"),
    (19045, "22h2"),
    (22000, "21h2"),
    (22621, "22h2"),
    (22631, "23h2"),
    (26100, "24h2"),
]


def seed_mappings(apps, schema_editor):
    WindowsBuildMapping = apps.get_model("compliance", "WindowsBuildMapping")
    WindowsBuildMapping.objects.bulk_create([
        WindowsBuildMapping(build=build, channel=channel)
        for build, channel in INITIAL_MAPPINGS
    ])


def unseed_mappings(apps, schema_editor):
    WindowsBuildMapping = apps.get_model("compliance", "WindowsBuildMapping")
    WindowsBuildMapping.objects.filter(build__in=[b for b, _ in INITIAL_MAPPINGS]).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory_base', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComplianceRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
                ('type', models.CharField(choices=[('software', 'Logiciel'), ('security', 'Sécurité')], max_length=50)),
                ('severity', models.CharField(choices=[('critical', 'Critique'), ('high', 'Élevée'), ('medium', 'Moyenne'), ('low', 'Faible')], default='medium', max_length=50)),
                ('priority', models.IntegerField()),
                ('logic', models.JSONField()),
                ('enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['priority']},
        ),
        migrations.CreateModel(
            name='ComplianceTarget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_type', models.CharField(choices=[('all', 'Tous les assets'), ('group', "Groupe d'assets"), ('tag', 'TAG')], default='all', max_length=50)),
                ('target_value', models.CharField(blank=True, max_length=255, null=True)),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='targets', to='compliance.compliancerule')),
            ],
            options={'ordering': ['rule']},
        ),
        migrations.CreateModel(
            name='ComplianceResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('compliant', 'Conforme'), ('non_compliant', 'Non conforme'), ('unknown', 'Inconnu')], default='unknown', max_length=50)),
                ('detail', models.JSONField(blank=True, null=True)),
                ('evaluated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compliance_results', to='inventory_base.inventorybase')),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='compliance.compliancerule')),
            ],
            options={'ordering': ['-evaluated_at']},
        ),
        migrations.AddConstraint(
            model_name='complianceresult',
            constraint=models.UniqueConstraint(fields=['asset', 'rule'], name='unique_compliance_result_per_asset_rule'),
        ),
        migrations.CreateModel(
            name='EOLCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product', models.CharField(max_length=100)),
                ('cycle', models.CharField(max_length=50)),
                ('eol', models.CharField(blank=True, max_length=20, null=True)),
                ('is_eol', models.BooleanField(default=False)),
                ('support', models.CharField(blank=True, max_length=20, null=True)),
                ('latest', models.CharField(blank=True, max_length=50, null=True)),
                ('fetched_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name='eolcache',
            constraint=models.UniqueConstraint(fields=['product', 'cycle'], name='unique_eol_cache_product_cycle'),
        ),
        migrations.CreateModel(
            name='AssetEOLStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product', models.CharField(blank=True, max_length=100, null=True)),
                ('cycle', models.CharField(blank=True, max_length=50, null=True)),
                ('eol', models.CharField(blank=True, max_length=20, null=True)),
                ('is_eol', models.BooleanField(default=False)),
                ('support', models.CharField(blank=True, max_length=20, null=True)),
                ('latest', models.CharField(blank=True, max_length=50, null=True)),
                ('fetched_at', models.DateTimeField(auto_now=True)),
                ('asset', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='eol_status', to='inventory_base.inventorybase')),
            ],
        ),
        migrations.CreateModel(
            name='WindowsBuildMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('build', models.IntegerField(help_text='Numéro de build Windows (ex: 22621)', unique=True)),
                ('channel', models.CharField(help_text='Canal endoflife.date (ex: 22h2)', max_length=20)),
            ],
            options={'ordering': ['build']},
        ),
        migrations.RunPython(seed_mappings, reverse_code=unseed_mappings),
    ]
