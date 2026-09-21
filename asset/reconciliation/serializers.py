from rest_framework import serializers


class ReconciliationRequestSerializer(serializers.Serializer):
    """
    Reconciliation criteria: any subset of asset fields usable to match an
    existing asset (e.g. uuid, serial, srcmac, srcip, name)
    """

    class Meta:
        ref_name = "ReconciliationRequest"


class ReconciliationResponseSerializer(serializers.Serializer):
    """
    id: the matched asset's id, or False if no asset matched
    """

    id = serializers.JSONField()


class ReconciliationErrorSerializer(serializers.Serializer):
    error = serializers.CharField()
