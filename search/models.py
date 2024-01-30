from django.db import models

from django.db.models.fields.json import JSONField
from django.contrib.auth.models import User, Group


class Search(models.Model):
    """
    Search model class definition

    The model will contain the following info
    - Search
    - Last updated
    - Visibility
    - Description
    - Allow modification by group members
    """

    visibility_choices = [
        ("public", "Public"),
        ("private_personal", "Private (Personal)"),
        ("private_group", "Private (Group)"),
    ]

    search = JSONField()
    last_updated = models.DateTimeField(auto_now=True)
    visibility = models.CharField(
        max_length=20, choices=visibility_choices, default="private_personal"
    )
    description = models.TextField()
    allow_group_modification = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    groups = models.ManyToManyField(Group, blank=True)
