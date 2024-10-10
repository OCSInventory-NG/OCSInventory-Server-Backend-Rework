from rest_framework import serializers
from .models import FileManager


class FileManagerSerializer(serializers.ModelSerializer):
    """
    Serializer for the FileManager model.
    """

    class Meta:
        model = FileManager
        fields = "__all__"
        read_only_fields = ["created_at", "modified_at", "filesize", "mimetype"]