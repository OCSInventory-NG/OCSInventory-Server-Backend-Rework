from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Rule(models.Model):
    TRIGGER_CHOICES = [
        ("inventory_received", "Inventory Received"),
        ("user_login", "User Login"),
        ("netdevice_received", "Netdevice Received"),
    ]

    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    priority = models.IntegerField()
    break_on_match = models.BooleanField(default=False)
    logic = models.JSONField()
    enabled = models.BooleanField(default=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["trigger", "priority"]


class Action(models.Model):
    ACTION_CHOICES = [
        ("set", "Set"),
    ]

    rule = models.ForeignKey(
        Rule, related_name="actions", on_delete=models.CASCADE, null=True
    )
    priority = models.IntegerField()
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    # Define a GenericForeignKey to handle actions on different models
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_slug = models.CharField(null=True, max_length=100)

    field = models.CharField(max_length=255)
    value = models.JSONField()

    class Meta:
        ordering = ["rule", "priority"]


@receiver(post_delete, sender=Rule)
def adjust_rule_order_on_delete(sender, instance, **kwargs):
    Rule.objects.filter(
        trigger=instance.trigger,
        priority__gt=instance.priority,
    ).update(priority=F("priority") - 1)


@receiver(post_delete, sender=Action)
def adjust_action_order_on_delete(sender, instance, **kwargs):
    if instance.rule_id is None:
        return

    Action.objects.filter(
        rule_id=instance.rule_id,
        priority__gt=instance.priority,
    ).update(priority=F("priority") - 1)
