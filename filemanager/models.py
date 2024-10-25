from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from uuid import uuid4


class FileManager(models.Model):
    """
    File manager model to track uploaded files and their metadata.
    """

    def upload_to(instance, filename):
        """
        Generate the upload path for the file.
        """
        return f"{instance.linked_model}/{instance.created_at.year}/{instance.created_at.month}/{instance.uuid}/{filename}"

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=upload_to)
    filesize = models.IntegerField()
    mimetype = models.CharField(max_length=100)
    linked_model = models.CharField(max_length=100)
    uuid = models.UUIDField(default=uuid4, editable=False)


@receiver(post_delete, sender=FileManager)
def delete_file_on_entry_delete(sender, instance, **kwargs):
    """
    Delete file from system when the associated FileManager instance is deleted
    """
    if instance.file:
        instance.file.delete(save=False)
