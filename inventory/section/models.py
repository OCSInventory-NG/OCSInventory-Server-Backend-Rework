from django.db import models
from inventory.template.models import Template


# Create your models here.
class Section(models.Model):
    """
    Template model class definition

    The model will contain the following info
    - Name
    - Operating system
    - Sections template link
    - Last update (Read Only)
    """

    RETRIVAL_CHOICES = (
        ("FILE", "Read file"),
        ("BASH", "Bash command"),
        ("PW", "Powershell command"),
        ("CMD", "Cmd command"),
    )

    name = models.CharField(max_length=50)
    retrival_method = models.CharField(
        max_length=4,
        choices=RETRIVAL_CHOICES,
        default="FILE"
    )
    target = models.CharField(
        max_length=255
    )
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
