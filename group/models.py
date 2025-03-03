from django.db import models
from django.contrib.auth.models import Group

Group.add_to_class("is_protected", models.BooleanField(default=False))