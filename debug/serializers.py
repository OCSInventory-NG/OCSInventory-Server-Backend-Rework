from rest_framework import serializers


class DebugCallSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
    )
    path = serializers.CharField(max_length=2048)


class DebugResolveSerializer(serializers.Serializer):
    calls = DebugCallSerializer(many=True, allow_empty=True)
