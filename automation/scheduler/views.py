from automation.scheduler.models import Scheduler
from automation.scheduler.serializers import SchedulerSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions

# Create your views here.
class SchedulerViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Scheduler.objects.all()
    serializer_class = SchedulerSerializer
    model = Scheduler
