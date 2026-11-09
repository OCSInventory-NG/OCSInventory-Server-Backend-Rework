from django.db import migrations, models


class Migration(migrations.Migration):
    """Apart from 0009: PostgreSQL alters no table its transaction changed rows of."""

    dependencies = [
        ("software", "0009_dictionary_signature"),
    ]

    operations = [
        migrations.AlterField(
            model_name="softwaredictionary",
            name="signature",
            field=models.CharField(
                editable=False, max_length=64, null=True, unique=True
            ),
        ),
    ]
