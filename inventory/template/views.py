from inventory.template.models import Template
from inventory.template.serializers import TemplateSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import status
from rest_framework.response import Response


class TemplateViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    model = Template

    def create(self, request, *args, **kwargs):
        """
        Handle post request, suitable for single and multi creation
        """
        try:
            if request.query_params.get("delete"):
                legacy_tempalte = Template.objects.filter(name="Legacy", os="LEG")[0]
                serializer = TemplateSerializer(legacy_tempalte)
                for id in request.data["ids"]:
                    if id == serializer.data["id"]:
                        return Response(
                            {"detail": "Legacy template cannot be deleted"},
                            status.HTTP_401_UNAUTHORIZED,
                        )
                    instance = self.model.objects.get(id=id)
                    self.perform_destroy(instance)
            else:
                serializer = self.get_serializer(
                    data=request.data, many=isinstance(request.data, list)
                )
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)
        except Exception as e:
            return Response(
                {"failed": request.data, "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"success": "200"}, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """
        Handle delete request
        """
        instance = self.get_object()
        legacy_tempalte = Template.objects.filter(name="Legacy", os="LEG")[0]
        serializer = TemplateSerializer(legacy_tempalte)
        if instance.id == serializer.data["id"]:
            return Response(
                {"detail": "Legacy template cannot be deleted"},
                status.HTTP_401_UNAUTHORIZED,
            )
        return super().destroy(request)
