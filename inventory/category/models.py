from django.db import models
from inventory.section.models import Section


# Create your models here.
class Category(models.Model):
    """
    Category model class definition

    The model will contain the following info
    - Name
    - Description
    """

    name = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    sections = models.ManyToManyField(Section, blank=True)
