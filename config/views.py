from config.models import Config
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from config.serializers import ConfigSerializer

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

    def _perform_update(self, name, data):
        """
        performs update or create if no correponding instance found

        Args:
            name ([str]): config element name, must be unique
            data ([dict]): set of values

        Returns:
            [serialized]
        """
        created, updated, deleted, errors = []
        try :
            instance = Config.objects.get(name=name)
            updated += [name]
        except :
            instance = None
            created += [name]

        serialized = self.serializer_class(instance, data=data)
        serialized.is_valid()
        serialized.save()

        return serialized, created, updated


    def put(self, request):
        data = request.data
        # MULTIPLE ENTRIES
        if isinstance(data, list):
            for elem in data:
                self._perform_update(elem['name'], elem)

        # SINGLE ENTRY
        else :
            name = data.get('name', None)
            self._perform_update(name, data)

        return Response({'msg': 'updated'})