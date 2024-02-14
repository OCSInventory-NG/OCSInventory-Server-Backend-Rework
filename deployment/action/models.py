from django.db import models
from deployment.package.models import Package


class DeploymentAction(models.Model):
    """
    Action model class definition

    The model will contain the following info
    - Package ID
    - Name
    - Priority order
    - Date of creation
    - Type of action
    - Command
    - File
    """

    package = models.ForeignKey(
        Package, related_name="actions_list", on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=128)
    priority = models.IntegerField()
    date_created = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=128)
    command = models.CharField(max_length=200)
    file = models.FileField(upload_to="files/", null=True, blank=True)
