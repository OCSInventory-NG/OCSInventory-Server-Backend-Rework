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
    identifier = models.CharField(max_length=100, primary_key=True)
    ip = models.GenericIPAddressField()
    subnets = JSONField(default=list)
    notes = models.TextField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    total_scanned = models.IntegerField(default=0, null=True)
    total_found = models.IntegerField(default=0, null=True)
    last_scan_date = models.DateTimeField(null=True)