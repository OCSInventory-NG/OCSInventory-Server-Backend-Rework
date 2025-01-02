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

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        legacy_tempalte = Template.objects.filter(name="Legacy", os="LEG")[0]
        serializer = TemplateSerializer(legacy_tempalte)
        if instance.id == serializer.data["id"]:
            return Response(
                {"detail": "Legacy template cannot be deleted"},
                status.HTTP_401_UNAUTHORIZED,
            )
        return super().destroy(request)
