from rest_framework import serializers
from .models import FileManager
import mimetypes
from uuid import uuid4


class FileManagerSerializer(serializers.ModelSerializer):
    """
    Serializer for the FileManager model.
    """
    class Meta:
        model = FileManager
        fields = [
            "id",
            "created_at",
            "modified_at",
            "name",
            "file",
            "filesize",
            "mimetype",
            "linked_model",
            "uuid",
        ]


class FileUploadMixin(serializers.Serializer):
    file = serializers.FileField(required=False)

    def create(self, validated_data):
        """
        Create method to handle file upload
        """
        validated_data = self.handle_file_upload(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Update method to handle file upload
        """
        validated_data = self.handle_file_upload(validated_data)
        return super().update(instance, validated_data)

    def handle_file_upload(self, validated_data):
        """
        Handles file compression and creates a FileManager object
        """
        file = validated_data.pop('uploaded_file', None)
        if file:
            mimetype = mimetypes.guess_type(file.name)[0]
            compressed_file = self.compress(file)
            uuid = uuid4()
            file_manager = FileManager.objects.create(
                file=compressed_file,
                name=compressed_file.name,
                filesize=compressed_file.size,
                mimetype=mimetype,
                linked_model=self.Meta.model.__name__,
                uuid=uuid
            )
            validated_data["file"] = file_manager
        return validated_data

    def compress(self, file):
        """
        Default compression logic here, override in child classes as needed.
        See DeploymentActionSerializer for an example of overriding this method.
        """
        return file
