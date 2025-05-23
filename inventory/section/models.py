from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from inventory.template.models import Template


# Create your models here.
class Section(models.Model):
    """
    Section model class definition

    The model will contain the following info
    - Name
    - Retrival method
    - Retrival output
    - Template link
    - Last update (Read Only)
    """

    RETRIEVAL_CHOICES = (
        ("FILE", "Read file"),
        ("BASH", "Bash command"),
        ("PW", "Powershell command"),
        ("CMD", "Cmd command"),
        ("SNMP_WALK", "Walk the SNMP tree starting from a specific OID"),
        ("SNMP_GET", "Get a specific OID"),
    )

    RETRIEVAL_OUTPUT = (
        ("PTXT", "Plain text"),
        ("JSON", "JSON format"),
        ("TBLE", "Table format"),
        ("REGX", "Regex processing"),
        ("GREP", "Grep command output"),
    )

    name = models.CharField(max_length=50)
    retrieval_method = models.CharField(
        max_length=10, choices=RETRIEVAL_CHOICES, default="FILE"
    )
    retrieval_output = models.CharField(
        max_length=4, choices=RETRIEVAL_OUTPUT, default="JSON"
    )
    target = models.CharField(max_length=255)
    template = models.ForeignKey(
        Template, related_name="sections", on_delete=models.CASCADE, default=1
    )
    options = models.JSONField(null=True)


@receiver(post_save, sender=Section)
def update_template_on_section_save(sender, instance, **kwargs):
    """
    Updates template's last_update field when a section is saved
    """
    if instance.template:
        instance.template.save()


@receiver(post_delete, sender=Section)
def update_template_on_section_delete(sender, instance, **kwargs):
    """
    Updates template's last_update field when a section is deleted
    """
    if instance.template:
        instance.template.save()
