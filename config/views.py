from config.models import Config
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from config.serializers import ConfigSerializer
from rest_framework.exceptions import ValidationError


class ConfigViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [IsAuthenticated]

    queryset = Config.objects.all()
    serializer_class = ConfigSerializer

    def _perform_update(self, elm):
        print(elm)
        pk = Config.objects.update(**elm)
        print(pk)
        db_instance = Config.objects.filter(pk=pk).first()
        print(db_instance)

    def put(self, request):
        data = request.data
        serialized = self.serializer_class(data=data, many=isinstance(data, list))
        serialized.is_valid(raise_exception=True)
        if isinstance(data, list):  # Update multiple elements
            for elm in serialized.validated_data:
                self._perform_update(elm)
        else:  # Update one element
            self._perform_update(serialized.validated_data)
        return Response({'msg': 'updated'})