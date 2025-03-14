from deployment.action.models import DeploymentAction
from django.db.models import F
from rest_framework import serializers
from filemanager.serializers import FileManagerSerializer, FileUploadMixin
from django.core.files.base import ContentFile
import tarfile
import zipfile
from io import BytesIO
import os


class ActionSerializer(FileUploadMixin, serializers.ModelSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ModelSerializer])
    """
    file = FileManagerSerializer(read_only=True, required=False)
    uploaded_file = serializers.FileField(write_only=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = DeploymentAction
        fields = [
            "id",
            "package",
            "name",
            "priority",
            "date_created",
            "action_type",
            "command",
            "file",
            "uploaded_file",
            "original_file_name",
        ]
        extra_kwargs = {
            "file": {"required": False},
            "original_file_name": {"required": False},
        }

    def custom_validate(self, data):
        """
        Perform custom validation on the DeploymentAction data.
        """
        if (
            DeploymentAction.objects.filter(package=data["package"])
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            # adjust priorities if there's a conflict
            # if the current priority is being updated to a higher priority
            if self.instance and data["priority"] < self.instance.priority:

                DeploymentAction.objects.filter(
                    package=data["package"],
                    priority__lt=self.instance.priority,
                    priority__gte=data["priority"],
                ).exclude(pk=self.instance.pk if self.instance else None).update(
                    priority=F("priority") + 1
                )

            # if the current priority is being updated to a lower priority
            elif self.instance and data["priority"] > self.instance.priority:
                DeploymentAction.objects.filter(
                    package=data["package"],
                    priority__lte=data["priority"],
                    priority__gt=self.instance.priority,
                ).exclude(pk=self.instance.pk if self.instance else None).update(
                    priority=F("priority") - 1
                )
            # adjust priorities of existing configs
            else:
                DeploymentAction.objects.filter(
                    package=data["package"], priority__gte=data["priority"]
                ).update(priority=F("priority") + 1)
        return data

    def create(self, validated_data):
        """
        Overriding the create method to manage action priority.
        """
        validated_data["priority"] = (
            DeploymentAction.objects.filter(package=validated_data["package"]).count()
            + 1
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Overriding the update method to manage action priority.
        """
        validated_data = self.custom_validate(validated_data)
        return super().update(instance, validated_data)

    def compress(self, file):
        """
        Overriding FileUploadMixin compress method
        Compresses the provided file based on the specified operating system type.

        Args:
            file (django.core.files.uploadedfile.UploadedFile): The file to be
            compressed.

        Returns:
            django.core.files.base.ContentFile: The compressed file.

        Raises:
            ValueError: If the ostype is not "LIN", "MAC", or "WIN".

        Example:
            compressed_file = self.compress(file)
        """
        buffer = BytesIO()

        # getting os type from the package
        ostype = self.validated_data.get("package").target_os

        if ostype == "LIN" or ostype == "MAC":
            # Create a new tar file in the buffer
            with tarfile.open(fileobj=buffer, mode="w:gz") as tar_file:
                # Read the content of the file field
                file_content = file.read()

                # Create a tarinfo object
                tarinfo = tarfile.TarInfo(name=file.name)
                tarinfo.size = len(file_content)

                # Add the file to the tar file
                tar_file.addfile(tarinfo, BytesIO(file_content))

            # Get the value of the buffer
            compressed_buffer_value = buffer.getvalue()

            # Create a ContentFile from the buffer value
            compressed_file = ContentFile(
                compressed_buffer_value, name=f"{os.path.splitext(file.name)[0]}.tar.gz"
            )

        elif ostype == "WIN":
            # Create a new zip file in the buffer
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # Read the content of the file field
                file_content = file.read()

                # Add the file to the zip file with the original file name
                zip_file.writestr(file.name, file_content)

            # Get the value of the buffer
            compressed_buffer_value = buffer.getvalue()

            # Create a ContentFile from the buffer value
            compressed_file = ContentFile(
                compressed_buffer_value, name=f"{os.path.splitext(file.name)[0]}.zip"
            )

        else:
            raise ValueError("Invalid ostype. Expected 'LIN', 'MAC', or 'WIN'.")

        return compressed_file
