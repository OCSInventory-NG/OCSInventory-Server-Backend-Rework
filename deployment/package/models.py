from django.db import models


class Package(models.Model):
    """
    Package model class definition

    The model will contain the following info
    - Name
    - Description
    - Date of creation
    - Target OS (limited by OS_CHOICES list)
    """

    OS_CHOICES = (
        ("WIN", "Windows"),
        ("LIN", "Linux"),
        ("MAC", "Mac"),
    )

    name = models.CharField(max_length=128)
    description = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    target_os = models.CharField(max_length=3, choices=OS_CHOICES, default="WIN")
