from django.db import models
from deployment.package.models import Package


class Result(models.Model):
    """
    Result model class definition

    The model will contain the following info
    - Package ID
    - Name
    - Date of creation
    """

    package = models.ForeignKey(
        Package, related_name="result", on_delete=models.CASCADE, null=True
    )
    name = models.CharField(max_length=128)
    check_action = models.CharField(max_length=128)
    result = models.CharField(max_length=200)
    date_created = models.DateTimeField(auto_now_add=True)
