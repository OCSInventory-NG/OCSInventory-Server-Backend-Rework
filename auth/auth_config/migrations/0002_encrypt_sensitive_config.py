from django.db import migrations
from ocsinventory_backend.ocs_framework.crypto import decrypt, encrypt

# Hard coded on purpose: a migration is a historical snapshot and must not
# change its behaviour when the auth backends declare new fields.
SENSITIVE_FIELDS = ("CLIENT_SECRET", "BIND_PASSWORD")


def _apply_to_sensitive_values(apps, func):
    """
    Apply func to every sensitive value stored in the AuthConfig table.

    The historical model has no custom save(), so the values written here are
    exactly the ones func returns. Values already in the target state are left
    untouched, which makes the operation safe to replay.
    """
    AuthConfig = apps.get_model("auth_config", "AuthConfig")
    for auth_config in AuthConfig.objects.all():
        config = auth_config.config
        if not isinstance(config, dict):
            continue
        changed = False
        for field in SENSITIVE_FIELDS:
            value = config.get(field)
            if not value:
                continue
            new_value = func(value)
            if new_value != value:
                config[field] = new_value
                changed = True
        if changed:
            auth_config.config = config
            auth_config.save(update_fields=["config"])


def encrypt_sensitive_config(apps, schema_editor):
    _apply_to_sensitive_values(apps, encrypt)


def decrypt_sensitive_config(apps, schema_editor):
    _apply_to_sensitive_values(apps, decrypt)


class Migration(migrations.Migration):

    dependencies = [
        ("auth_config", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(encrypt_sensitive_config, decrypt_sensitive_config),
    ]
