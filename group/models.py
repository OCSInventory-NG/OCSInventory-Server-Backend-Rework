from django.contrib.auth.models import Group
from django.db import models

Group.add_to_class("is_protected", models.BooleanField(default=False))
