# OCSInventory-Server-Backend-Rework/user/migrations/0002_userauthprofile.py
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAuthProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "last_login_method",
                    models.CharField(
                        choices=[
                            ("OIDC", "OIDC"),
                            ("CAS", "CAS"),
                            ("LDAP", "LDAP"),
                            ("LOCAL", "LOCAL"),
                            ("UNKNOWN", "UNKNOWN"),
                        ],
                        default="UNKNOWN",
                        max_length=16,
                    ),
                ),
                (
                    "last_login_backend",
                    models.CharField(blank=True, null=True, max_length=255),
                ),
                ("last_login_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
