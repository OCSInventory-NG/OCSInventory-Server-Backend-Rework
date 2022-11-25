from autoaction.tasks.models import Tasks
from autoaction.tasks.serializers import TasksSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions

# Create your views here.
class TasksViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Tasks.objects.all()
    serializer_class = TasksSerializer
    model = Tasks
