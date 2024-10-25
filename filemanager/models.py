from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class FileManager(models.Model):
    """
    File manager model to track uploaded files and their metadata.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255)
    object = models.FileField(upload_to="files/")
    filesize = models.IntegerField()
    mimetype = models.CharField(max_length=100)
    linked_model = models.CharField(max_length=100, null=True, blank=True)

    def create(self, validated_data):
        """
        Save the file to the file manager and return the instance.
        """
        super().create(validated_data)


@receiver(post_delete, sender=FileManager)
def delete_file_on_entry_delete(sender, instance, **kwargs):
    """
    Delete file from system when the associated FileManager instance is deleted
    """
    if instance.file:
        instance.file.delete(save=False)
