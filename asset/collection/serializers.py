from rest_framework import serializers


class CollectionResponseSerializer(serializers.Serializer):
    """
    Response shape on successful asset creation/update
    """

    message = serializers.CharField()
    id = serializers.IntegerField()


class CollectionErrorSerializer(serializers.Serializer):
    error = serializers.CharField()
