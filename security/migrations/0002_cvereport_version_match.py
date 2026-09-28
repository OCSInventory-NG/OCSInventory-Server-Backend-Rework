from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cvereport",
            name="version_match",
            field=models.CharField(
                choices=[
                    (
                        "matched",
                        "Version installée confirmée dans la plage affectée",
                    ),
                    (
                        "unknown",
                        "Plage affectée non comparable (CVE conservée par défaut)",
                    ),
                ],
                default="unknown",
                max_length=10,
            ),
        ),
    ]
