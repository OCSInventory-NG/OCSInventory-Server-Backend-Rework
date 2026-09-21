from rest_framework import serializers


class LegacyResponseSerializer(serializers.Serializer):
    """
    Response shape on successful legacy asset creation/update
    """

    message = serializers.CharField()
    id = serializers.IntegerField()


class LegacyErrorSerializer(serializers.Serializer):
    error = serializers.CharField()
