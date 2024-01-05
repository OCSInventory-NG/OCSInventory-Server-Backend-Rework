from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Rule(models.Model):
    TRIGGER_CHOICES = [
        ('inventory_received', 'Inventory Received'),
        ('user_login', 'User Login'),
    ]

    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    logic = models.JSONField()
    enabled = models.BooleanField(default=True)


class Action(models.Model):
    ACTION_CHOICES = [
        ('set', 'Set'),
    ]

    rule = models.ForeignKey(Rule, related_name='actions', on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)

    # Define a GenericForeignKey to handle actions on different models
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                     null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_slug = models.CharField(null=True, max_length=100)

    field = models.CharField(max_length=50)
    value = models.CharField(max_length=255)
