from rest_framework import permissions, viewsets

from .models import FileManager
from .serializers import FileManagerSerializer


class FileManagerViewSet(viewsets.ModelViewSet):
    """
    Viewset for the FileManager model.
    """

    queryset = FileManager.objects.all()
    serializer_class = FileManagerSerializer
    permission_classes = [permissions.IsAuthenticated]
