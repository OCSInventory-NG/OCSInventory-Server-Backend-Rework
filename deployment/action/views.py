import logging
import os
import tarfile
import zipfile
from io import BytesIO

from deployment.action.models import DeploymentAction
from deployment.action.serializers import ActionSerializer
from deployment.package.models import Package
from deployment.package.serializers import PackageSerializer
from django.core.files.base import ContentFile
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response


class ActionViewSet(viewsets.OCSViewSet):
    """
    View behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    LOGGER = logging.getLogger(__name__)

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = DeploymentAction.objects.all()
    serializer_class = ActionSerializer
    model = DeploymentAction
    filterset_fields = [
        "id",
        "package",
        "name",
        "priority",
        "date_created",
        "action_type",
        "command",
    ]

    def compress(self, file, ostype):
        """
        Compresses the provided file based on the specified operating system type.

        Args:
            file (django.core.files.uploadedfile.UploadedFile): The file to be
            compressed.
            ostype (str): The operating system type. Should be "LIN", "MAC",
            or "WIN".

        Returns:
            django.core.files.base.ContentFile: The compressed file.

        Raises:
            ValueError: If the ostype is not "LIN", "MAC", or "WIN".

        Example:
            compressed_file = self.compress(file, "LIN")
        """
        # Create a buffer to hold the compressed file
        buffer = BytesIO()

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
            raise ValueError("Invalid ostype. Expected 'linux' or 'windows'.")

        return compressed_file

    def create(self, request, *args, **kwargs):
        """
        Creates a new DeploymentAction instance.

        Extracts data from the request, compresses the uploaded file based
        on the target OS, validates the data, and saves the new action if valid.

        Args:
            request (rest_framework.request.Request): The request object containing
            the data.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            rest_framework.response.Response: A response indicating the success
            or failure of the creation.

        Example:
            response = self.create(request)
        """
        # Extract data from the request
        data = request.data
        # Initialize an empty list to collect any errors
        errors = []
        # Log the creation attempt with the package ID
        self.LOGGER.info("Creating action for package %s", data["package"])

        try:
            # Retrieve the package instance using the provided package ID
            package = Package.objects.get(id=data["package"])
            # Serialize the package instance to get its data as a dictionary
            packageData = PackageSerializer(package).data
            # Compress the uploaded file based on the target OS specified in the package
            # data
            if "file" in data.keys():
                data["file"] = self.compress(data["file"], packageData["target_os"])

            # Create a serializer instance with the modified data
            actionSerializer = ActionSerializer(data=data)
            # Validate the data; if invalid, raise an exception
            if actionSerializer.is_valid(raise_exception=True):
                # Save the new action to the database if the data is valid
                actionSerializer.save()

        except ValidationError as ve:
            # If there is a validation error, add it to the errors list and log the
            # error
            errors.append(f"Error creating action: {ve}")
            self.LOGGER.error(f"Error creating action: {ve}")
            # Return a 400 Bad Request response with the error message
            return Response({"error": errors}, status=400)

        except Exception as e:
            # Log any other exceptions that occur and add the error to the response
            self.LOGGER.error(f"Error creating action: {e}")
            return Response({"error": f"Error creating action {e}"}, status=500)

        # If the action is created successfully, return a 201 Created response
        return Response({"message": "Action created successfully"}, status=201)
