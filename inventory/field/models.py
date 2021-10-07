from django.db import models
from inventory.section.models import Section


# Create your models here.
class Field(models.Model):
    """
    Field model class definition

    The model will contain the following info
    - Name
    - Retrival value

    Some explanation on the retrival value :
    - Depending on the retrival output, the value is diffrent
    - If the output is JSON we expect a JSON position
    - If the output is Plain Text we expect a line number
    - If the output is a table we expect an index
    """

    name = models.CharField(max_length=50)
    retrival_value = models.CharField(max_length=255)
    section = models.ForeignKey(Section, related_name="fields", on_delete=models.CASCADE)
