from django.db import models
from django.db.models.fields.json import JSONField
from ocsinventory_backend.ocs_framework.models import RestrictVisibility


class Search(RestrictVisibility):
    """
    Search model class definition

    Extends the RestrictVisibility model to handle visibility restriction

    The model will contain the following info
    - Search
    - Last updated
    - Name
    - Description
    """

    search = JSONField()
    last_updated = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=50)
    description = models.TextField()
