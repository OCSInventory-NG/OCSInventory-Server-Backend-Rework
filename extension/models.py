from django.db import models

class Extension(models.Model):
    """
    Extension model class definition

    The model will contain the following info
    - Name
    - Description
    - Version
    - Author
    - Enabled
    """
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    version = models.CharField(max_length=255)
    author = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=False)
