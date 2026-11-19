from django.contrib.auth.models import Group
from django.db import models


class GroupProtection(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name="protection",
    )
    is_protected = models.BooleanField(default=False)


class GroupAssetScope(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name="asset_scope",
    )
    asset_groups = models.ManyToManyField(
        "asset_group.AssetGroup",
        related_name="scoped_user_groups",
        blank=True,
    )
