from django.contrib.auth.models import Group
from django.db import models


class GroupProtection(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name="protection",
    )
    is_protected = models.BooleanField(default=False)
