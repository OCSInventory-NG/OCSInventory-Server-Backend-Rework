from deployment.package.models import Package
from django.db import models


class DeploymentAction(models.Model):
    def upload_to(instance, filename):
        return f"files/{instance.package.id}/{filename}"

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
    - Original file name
    """

    package = models.ForeignKey(
        Package, related_name="actions_list", on_delete=models.CASCADE, null=True
    )
    name = models.CharField(max_length=128)
    priority = models.IntegerField()
    date_created = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=128)
    command = models.CharField(max_length=200)
    file = models.FileField(upload_to=upload_to, null=True, blank=True)
    original_file_name = models.CharField(max_length=128)
