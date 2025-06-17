from django.db import models


# Create your models here.
class Template(models.Model):
    """
    Template model class definition

    The model will contain the following info
    - Name
    - Operating system
    - Last update
    - Is protected (used to prevent deletion from the console)
    """

    OS_CHOICES = (
        ("LEG", "Legacy"),
        ("LIN", "Linux"),
        ("MAC", "Mac"),
        ("WIN", "Windows"),
        ("SNMP", "SNMP"),
    )

    name = models.CharField(max_length=50)
    os = models.CharField(max_length=4, choices=OS_CHOICES, default="WIN")
    last_update = models.DateTimeField(auto_now=True)
    is_protected = models.BooleanField(default=False)
