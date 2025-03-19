import mimetypes
from uuid import uuid4

from rest_framework import serializers

from .models import FileManager


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
        Handles file compression and creates/updates a FileManager object
        """
        file = validated_data.pop("uploaded_file", None)
        if file:
            # use fallback if mimetype can't be determined
            mimetype = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            compressed_file = self.compress(file)

            # update existing instance
            if self.instance and hasattr(self.instance, "file") and self.instance.file:
                file_manager = self.instance.file
                # delete old file from storage
                if file_manager.file:
                    storage = file_manager.file.storage
                    if storage.exists(file_manager.file.name):
                        storage.delete(file_manager.file.name)

                file_manager.file = compressed_file
                file_manager.name = compressed_file.name
                file_manager.filesize = compressed_file.size
                file_manager.mimetype = mimetype
                file_manager.save()
            else:
                # new file instance
                uuid = uuid4()
                file_manager = FileManager.objects.create(
                    file=compressed_file,
                    name=compressed_file.name,
                    filesize=compressed_file.size,
                    mimetype=mimetype,
                    linked_model=self.Meta.model.__name__,
                    uuid=uuid,
                )
            validated_data["file"] = file_manager
        return validated_data

    def compress(self, file):
        """
        Default compression logic here, override in child classes as needed.
        See DeploymentActionSerializer for an example of overriding this method.
        """
        return file
