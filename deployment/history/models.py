from django.db import models
from deployment.package.models import Package
from asset.base.models import Base


class DeploymentHistory(models.Model):
    """
    DeploymentHistory model class definition

    The model will contain the following info
    - Package ID
    - Asset ID
    - Date assigned
    - Status
    """

    package = models.ForeignKey(
        Package, related_name="deployment_history", on_delete=models.CASCADE
    )
    asset = models.ForeignKey(
        Base, related_name="deployment_history", on_delete=models.CASCADE
    )
    date_assigned = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=128)
