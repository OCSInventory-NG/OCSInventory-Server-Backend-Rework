from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Rule(models.Model):
    TRIGGER_CHOICES = [
        ("inventory_received", "Inventory Received"),
        ("user_login", "User Login"),
        ("netdevice_received", "Netdevice Received"),
    ]

    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    logic = models.JSONField()
    enabled = models.BooleanField(default=True)
    description = models.CharField(max_length=255, null=True, blank=True)


class Action(models.Model):
    ACTION_CHOICES = [
        ("set", "Set"),
    ]

    rule = models.ForeignKey(
        Rule, related_name="actions", on_delete=models.CASCADE, null=True
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.CharField(max_length=255, null=True, blank=True)
    # Define a GenericForeignKey to handle actions on different models
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_slug = models.CharField(null=True, max_length=100)

    field = models.CharField(max_length=255)
    value = models.JSONField()
