from django.apps import AppConfig


class SecurityConfig(AppConfig):
    """Known vulnerabilities of identified software (CVE detection)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "security"
