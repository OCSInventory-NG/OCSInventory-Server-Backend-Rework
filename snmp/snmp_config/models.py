from django.db import models


class SnmpConfig(models.Model):
    """
    SNMP configuration model class definition

    The model will contain the following info
    - Name
    - Version
    - User
    - Level
    - Password
    - Auth Protocol
    - Priv Protocol
    - Priv Password
    - Retries
    - Timeout
    - Subnets
    """

    SNMP_VERSIONS = [
        ("1", "SNMPv1"),
        ("2c", "SNMPv2c"),
        ("3", "SNMPv3"),
    ]

    AUTH_LEVELS = [
        ("noAuthNoPriv", "noAuthNoPriv"),
        ("authNoPriv", "authNoPriv"),
        ("authPriv", "authPriv"),
    ]

    AUTH_PROTOCOLS = [
        ("MD5", "MD5"),
        ("SHA", "SHA"),
        ("None", "None"),
    ]

    PRIV_PROTOCOLS = [
        ("DES", "DES"),
        ("AES", "AES"),
        ("None", "None"),
    ]

    name = models.CharField(max_length=128, null=False)
    version = models.CharField(max_length=3, choices=SNMP_VERSIONS, null=False)
    user = models.CharField(max_length=128, blank=True, null=True)
    auth_level = models.CharField(max_length=128, choices=AUTH_LEVELS,
                                  blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)
    auth_protocol = models.CharField(max_length=4, choices=AUTH_PROTOCOLS,
                                     blank=True, null=True)
    priv_protocol = models.CharField(max_length=4, choices=PRIV_PROTOCOLS,
                                     blank=True, null=True)
    priv_password = models.CharField(max_length=128, blank=True, null=True)
    retries = models.IntegerField(default=3)
    timeout = models.IntegerField(default=3)
    subnets = models.JSONField()
