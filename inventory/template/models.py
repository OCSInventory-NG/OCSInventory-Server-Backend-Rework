from django.db import models


# Create your models here.
class Template:
    """
    Template model class definition

    The model will contain the following info
    - Name
    - Operating system
    - Sections template link
    - Revision (Read Only)
    """
    OS_CHOICES = (
        ("WIN", "Windows"),
        ("LIN", "Linux"),
        ("MAC", "Mac"),
    )

    name = models.CharField(max_length=50)
    os = models.CharField(
        max_length=3,
        choices=OS_CHOICES,
        default="WIN"
    )
    revision = models.IntegerField()
