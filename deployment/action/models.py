from deployment.package.models import Package
from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver
from filemanager.models import FileManager


class DeploymentAction(models.Model):
    """
    Action model class definition

    The model will contain the following info
    - Package ID
    - Name
    - Priority order
    - Date of creation
    - Type of action
    - Command
    - File
    - Original file name
    """

    package = models.ForeignKey(
        Package, related_name="actions_list", on_delete=models.CASCADE, null=True
    )
    name = models.CharField(max_length=128)
    priority = models.IntegerField()
    date_created = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=128)
    command = models.CharField(max_length=200)
    file = models.ForeignKey(
        FileManager,
        on_delete=models.CASCADE,
        related_name="deployment_actions",
        null=True,
        blank=True,
    )
    original_file_name = models.CharField(max_length=128, null=True)


@receiver(post_delete, sender=DeploymentAction)
def adjust_priorities_on_delete(sender, instance, **kwargs):
    """
    This signal is triggered when a DeploymentAction is deleted.
    """
    configs_higher_priority = DeploymentAction.objects.filter(
        package=instance.package_id,
        priority__gt=instance.priority if instance.priority else 0,
    )

    # decrement their priorities
    configs_higher_priority.update(priority=F("priority") - 1)


@receiver(post_delete, sender=DeploymentAction)
def delete_associated_file(sender, instance, **kwargs):
    """
    Triggered when a DeploymentAction is deleted.
    """
    if instance.file:
        instance.file.delete()
