# Example: a REST serializer for the model above.

from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from .models import SampleComment


class SampleCommentSerializer(ModelSerializer):
    # Exposes the asset's name too, so the frontend doesn't need a second
    # request just to display it.
    asset_name = serializers.CharField(source="asset.name", read_only=True)

    class Meta:
        model = SampleComment
        fields = ["id", "asset", "asset_name", "message", "created_at"]
        read_only_fields = ["id", "asset_name", "created_at"]
