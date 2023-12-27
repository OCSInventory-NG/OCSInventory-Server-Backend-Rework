from django.db import models
from asset.base.models import Base

# Create your models here.
class Log(models.Model):
    
    SCOPE_CHOICES = (
        ('INVENTORY_BASE_INSERT', 'Inserting new items into the base inventory'),
        ('INVENTORY_BASE_UPDATE', 'Updating existing items in the base inventory'),
        ('INVENTORY_EXT_INSERT', 'Inserting new items into the extended inventory'),
        ('INVENTORY_EXT_UPDATE', 'Updating existing items in the extended inventory'),
        ('INVENTORY_BASE_ERR', 'Error related to the base inventory operations'),
        ('INVENTORY_EXT_ERR', 'Error related to the extended inventory operations'),
        ('DEPLOYMENT_ACK', 'Acknowledgment of a successful deployment'),
        ('DEPLOYMENT_ERR', 'Error during the deployment process'),
        ('CONFIG_UPDATE', 'Updating configuration settings'),
        ('CONFIG_ERR', 'Error related to configuration operations'),
        ('TEMPLATE_UPDATE', 'Updating templates for a process'),
        ('TEMPLATE_ERR', 'Error related to template operations'),
        ("UNKNOWN", "Unknown error happend (default)")
    )
    
    asset = models.ForeignKey(
        Base, 
        on_delete=models.CASCADE, 
        null=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    scope = models.CharField(
        max_length=30,
        choices=SCOPE_CHOICES,
        default="UNKNOWN"
    )
    comment = models.TextField(max_length=255)