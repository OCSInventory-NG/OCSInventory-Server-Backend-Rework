from django.db import models


class Package(models.Model):
    """
    Package model class definition

    The model will contain the following info
    - Name
    - Description
    - Date of creation
    - Target OS
    """

    name = models.CharField(max_length=128)
    description = models.CharField(max_length=128)
    date_created = models.DateTimeField(auto_now_add=True)
    target_os = models.CharField(max_length=128)
