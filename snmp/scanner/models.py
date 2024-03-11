from django.db import models
from django.db.models.fields.json import JSONField


class SnmpScanner(models.Model):
    """
    Model definition for SnmpScanner.

    Fields:
    - name: name of the scanner
    - ip : IP address of the scanner
    - subnets: list of subnets to scan

    """
    name = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    subnets = JSONField(default=list)
