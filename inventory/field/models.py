from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from inventory.section.models import Section


# Create your models here.
class Field(models.Model):
    """
    Field model class definition

    The model will contain the following info
    - Name
    - Retrival value

    Some explanation on the retrieval value :
    - Depending on the retrieval output, the value is diffrent
    - If the output is JSON we expect a JSON position
    - If the output is Plain Text we expect a line number
    - If the output is a table we expect an index
    """

    RETRIEVAL_CHOICES = (
        ("FILE", "Read file"),
        ("BASH", "Bash command"),
        ("PW", "Powershell command"),
        ("CMD", "Cmd command"),
    )

    RETRIEVAL_OUTPUT = (
        ("PTXT", "Plain text"),
        ("JSON", "JSON format"),
        ("TBLE", "Table format"),
        ("REGX", "Regex processing"),
        ("GREP", "Grep command output"),
    )

    name = models.CharField(max_length=50)
    retrieval_value = models.CharField(max_length=255)
    override_target = models.BooleanField(default=False, null=True)
    new_target = models.CharField(max_length=255, null=True)
    retrieval_method = models.CharField(
        max_length=4, choices=RETRIEVAL_CHOICES, null=True
    )
    retrieval_output = models.CharField(max_length=4, choices=RETRIEVAL_OUTPUT, null=True)
    section = models.ForeignKey(
        Section, related_name="fields", on_delete=models.CASCADE, default=1
    )
    options = models.JSONField(null=True)
    order = models.IntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


@receiver(post_save, sender=Field)
def update_template_on_field_save(sender, instance, **kwargs):
    """
    Updates template's last_update field when a field is saved
    """
    if instance.section and instance.section.template:
        instance.section.template.save()


@receiver(post_delete, sender=Field)
def update_template_on_field_delete(sender, instance, **kwargs):
    """
    Updates template's last_update field when a field is deleted
    """
    if instance.section and instance.section.template:
        instance.section.template.save()


@receiver(post_delete, sender=Field)
def adjust_order_on_delete(sender, instance, **kwargs):
    """
    This signal is triggered when a Field is deleted.
    """
    # if origin is Section, do not trigger the signal (nested deletion,
    # all field will be deleted at the same time and the signal will raise
    # a DoesNotExist exception when trying to decrement the order of an action)
    if isinstance(kwargs.get("origin"), Section):
        return

    new_order = Field.objects.filter(
        section=instance.section_id,
        order__gt=instance.order if instance.order else 0,
    )

    # decrement their order
    new_order.update(order=F("order") - 1)
