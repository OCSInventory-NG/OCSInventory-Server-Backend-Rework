# Example: a model, linked to a core asset.
#
# An extension can't add a field to a core model (InventoryBase) - it adds
# its own table and points at the core object with a ForeignKey instead.

from django.db import models


class SampleComment(models.Model):
    asset = models.ForeignKey(
        "inventory_base.InventoryBase",
        on_delete=models.CASCADE,
        related_name="sample_comments",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment on asset #{self.asset_id}"
