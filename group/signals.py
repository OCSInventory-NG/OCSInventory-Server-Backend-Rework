from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from group.models import GroupProtection


@receiver(post_save, sender=Group)
def ensure_group_protection(sender, instance, created, **kwargs):
    if created:
        GroupProtection.objects.get_or_create(group_id=instance.id)
