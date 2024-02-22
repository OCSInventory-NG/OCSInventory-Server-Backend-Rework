from django.contrib.auth.models import Group, User
from django.db import models


class RestrictVisibility(models.Model):
    """
    Abstract class to implement visibility restriction on child models
    """

    class Meta:
        abstract = True

    visibility_choices = [
        ("public", "Public"),
        ("private_personal", "Private (Personal)"),
        ("private_group", "Private (Group)"),
    ]

    visibility = models.CharField(
        max_length=20, choices=visibility_choices, default="private_personal"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    groups = models.ManyToManyField(Group, blank=True)
    allow_group_modification = models.BooleanField(default=False)
