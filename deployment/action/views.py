import logging
import os
import tarfile
import zipfile
from io import BytesIO

from deployment.action.models import DeploymentAction
from deployment.action.serializers import ActionSerializer
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
