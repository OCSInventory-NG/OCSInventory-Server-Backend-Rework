import hashlib

from auth.auth_config.models import AuthConfig, get_sensitive_config_fields
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ocsinventory_backend.ocs_framework.crypto import is_encrypted


class Command(BaseCommand):
    """Inspect and rotate the key encrypting the sensitive configuration values."""

    help = "Show, generate or rotate FIELD_ENCRYPTION_KEY"

    def add_arguments(self, parser):
        parser.add_argument(
            "--show",
            action="store_true",
            help="Print the key in use instead of its fingerprint",
        )
        parser.add_argument(
            "--generate",
            action="store_true",
            help="Print a new key without applying it",
        )
        parser.add_argument(
            "--rotate",
            type=str,
            metavar="NEW_KEY",
            help="Re-encrypt the stored secrets with NEW_KEY, keeping their value",
        )

    def handle(self, *args, **options):
        if options["generate"]:
            self.stdout.write(Fernet.generate_key().decode())
            return
        if options["rotate"]:
            self.rotate(options["rotate"])
            return
        self.show(options["show"])

    def show(self, reveal):
        """Report which key is in use, by fingerprint unless asked otherwise."""
        key = settings.FIELD_ENCRYPTION_KEY
        if not key:
            self.stdout.write("FIELD_ENCRYPTION_KEY is not set")
            return
        if reveal:
            self.stdout.write(key)
        else:
            digest = hashlib.sha256(key.encode()).hexdigest()[:16]
            self.stdout.write(f"fingerprint {digest}")

        try:
            readable, unreadable = self.count_values()
        except (TypeError, ValueError):
            raise CommandError(
                "FIELD_ENCRYPTION_KEY is not a valid Fernet key: the stored "
                "secrets can neither be read nor rotated. Restore the previous "
                "key, or generate a new one and set the secrets again."
            )
        self.stdout.write(f"{readable} secret(s) readable, {unreadable} unreadable")
        if unreadable:
            self.stdout.write(
                "The unreadable secrets were encrypted with another key. Restore "
                "that key, or set them again from the interface."
            )

    def count_values(self):
        """Count the stored secrets this key can and cannot decrypt."""
        fernet = Fernet(settings.FIELD_ENCRYPTION_KEY)
        sensitive_fields = get_sensitive_config_fields()
        readable = unreadable = 0
        for stored in AuthConfig.objects.values_list("config", flat=True):
            if not isinstance(stored, dict):
                continue
            for field in sensitive_fields:
                value = stored.get(field)
                if not value:
                    continue
                if not is_encrypted(value):
                    continue
                try:
                    fernet.decrypt(value.encode())
                    readable += 1
                except InvalidToken:
                    unreadable += 1
        return readable, unreadable

    def rotate(self, new_key):
        """
        Re-encrypt every secret with new_key.

        Reading goes through the model, which decrypts with the current key, so
        a secret that cannot be decrypted aborts the rotation instead of being
        silently destroyed.
        """
        try:
            Fernet(new_key)
        except (TypeError, ValueError):
            raise CommandError("NEW_KEY is not a valid Fernet key")

        sensitive_fields = get_sensitive_config_fields()
        configs = list(AuthConfig.objects.all())
        for auth_config in configs:
            for field in sensitive_fields:
                value = (auth_config.config or {}).get(field)
                if value and is_encrypted(value):
                    raise CommandError(
                        f"The '{field}' value of configuration "
                        f"'{auth_config.name}' cannot be decrypted with the "
                        "current key: rotation aborted"
                    )

        # only the configurations actually holding a secret are rewritten
        to_rotate = []
        secret_count = 0
        for auth_config in configs:
            found = sum(
                1 for field in sensitive_fields if (auth_config.config or {}).get(field)
            )
            if found:
                to_rotate.append(auth_config)
                secret_count += found

        settings.FIELD_ENCRYPTION_KEY = new_key
        for auth_config in to_rotate:
            auth_config.save(update_fields=["config"])

        self.stdout.write(f"{secret_count} secret(s) re-encrypted")
        self.stdout.write("Set FIELD_ENCRYPTION_KEY to the new key before restarting")
