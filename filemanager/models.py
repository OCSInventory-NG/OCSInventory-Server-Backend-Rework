from django.db import models
import mimetypes


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

    def save(self, *args, **kwargs):
        """
        Override the save method to calculate filesize and mimetype dynamically.
        """
        if self.object:
            self.filesize = self.object.size
            self.mimetype = mimetypes.guess_type(self.object.name)[0]

        self.name = self.object.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.mimetype}, {self.filesize} bytes)"
