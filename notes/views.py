from notes.models import Note
from notes.serializers import NoteSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class NoteViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # filters
    filterset_fields = ["object_slug", "object_id", "content_type"]

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    model = Note
