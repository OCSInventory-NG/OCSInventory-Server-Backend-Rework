from django.db import models


class AuthMethod(models.Model):
    """
    AuthMethod model class definition

    Fields :
    - Name
    - Auth Type : SSO or OTHER
    - Priority
    - Enabled
    """

    # define the choices for the type field
    TYPE_CHOICES = [
        ("SSO", "SSO"),  # applies to CAS and OIDC at the moment
        ("OTHER", "OTHER"),
    ]

    name = models.CharField(max_length=255, unique=True)
    auth_type = models.CharField(max_length=255, choices=TYPE_CHOICES)
    # priority only applies to methods using the login form, allow null for SSO methods
    priority = models.IntegerField(blank=True, null=True)
    enabled = models.BooleanField(default=False)
