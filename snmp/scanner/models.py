from asset.inventory_base.models import InventoryBase
from django.db import models
from django.db.models.fields.json import JSONField
from snmp.snmp_config.models import SnmpConfig


class SnmpScanner(models.Model):
    """
    Model definition for SnmpScanner.

    Fields:
    - name: name of the scanner
    - ip : IP address of the scanner
    - subnets: list of subnets to scan
    - notes : additional notes
    - last_updated : last updated date
    - total_scanned : total devices scanned
    - total_found : total devices found
    - last_scan_date : date of the last scan
    - configs : list of SNMP configurations
    - assets : list of assets within OCS
    """

    name = models.CharField(max_length=100, unique=True)
    ip = models.GenericIPAddressField()
    subnets = JSONField(default=list)
    notes = models.TextField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    total_scanned = models.IntegerField(default=0, null=True)
    total_found = models.IntegerField(default=0, null=True)
    last_scan_date = models.DateTimeField(null=True)
    configs = models.ManyToManyField(SnmpConfig, blank=True)
    assets = models.ManyToManyField(InventoryBase, blank=True)
