from rest_framework import serializers
from .models import FileManager
from rest_framework import serializers
from .models import FileManager
import mimetypes

class FileManagerSerializer(serializers.ModelSerializer):
    """
    Serializer for the FileManager model.
    """

    class Meta:
        model = FileManager
        fields = "__all__"
        read_only_fields = ["created_at", "modified_at", "filesize", "mimetype"]


class FileUploadMixin(serializers.Serializer):
    file = serializers.FileField(write_only=True, required=False)

    def handle_file_upload(self, validated_data):
        file = validated_data.pop('file', None)
        if file:
            mimetype = mimetypes.guess_type(file.name)[0]
            file_manager = FileManager.objects.create(
                object=file,
                name=file.name,
                filesize=file.size,
                mimetype=mimetype,
                # set linked model
                linked_model=self.Meta.model.__name__
            )
            validated_data["file"] = file_manager
        return validated_data
