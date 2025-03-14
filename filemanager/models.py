from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from uuid import uuid4
import os
import logging


class FileManager(models.Model):
    """
    File manager model to track uploaded files and their metadata.
    """

    LOGGER = logging.getLogger(__name__)

    def upload_to(instance, filename):
        """
        Generate the upload path for the file.
        """
        return (
            f"{instance.linked_model}/"
            f"{instance.created_at.year}/"
            f"{instance.created_at.month}/"
            f"{instance.uuid}/"
            f"{filename}"
        )

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
    Delete file and its parent directory when the associated FileManager
    instance is deleted
    """
    if instance.file:
        storage = instance.file.storage
        # delete file
        if storage.exists(instance.file.name):
            storage.delete(instance.file.name)

        # delete parent dir (1 dir = 1 file = 1 action)
        directory = (
            f"{instance.linked_model}/"
            f"{instance.created_at.year}/"
            f"{instance.created_at.month}/"
            f"{instance.uuid}"
        )
        try:
            full_path = os.path.join(storage.location, directory)
            if os.path.exists(full_path):
                os.rmdir(full_path)
        except OSError:
            FileManager.LOGGER.error(f"Failed to delete directory {directory}")
            pass
