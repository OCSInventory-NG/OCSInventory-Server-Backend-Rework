from django.db import models


class CpeProduct(models.Model):
    """An application of the NVD CPE dictionary, with its titles and known versions"""

    vendor = models.CharField(max_length=255)
    product = models.CharField(max_length=255)
    titles = models.JSONField(default=dict)
    versions = models.JSONField(default=list)
    popularity = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "product"], name="unique_cpe_product"
            )
        ]

    @property
    def key(self):
        return f"{self.vendor}:{self.product}"


class CpeToken(models.Model):
    """A word of a product's titles, weighted by its rarity over the whole index"""

    token = models.CharField(max_length=255, db_index=True)
    product = models.ForeignKey(
        CpeProduct, related_name="tokens", on_delete=models.CASCADE
    )
    weight = models.FloatField()


class CpeIndexState(models.Model):
    """Single row describing the CPE index currently loaded"""

    version = models.IntegerField(default=0)
    source_sha256 = models.CharField(max_length=64, blank=True, default="")
    source_date = models.CharField(max_length=64, blank=True, default="")
    synced_at = models.DateTimeField(null=True, blank=True)
    product_count = models.IntegerField(default=0)

    @classmethod
    def current(cls):
        return cls.objects.first() or cls()
