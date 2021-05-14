from rest_framework.viewsets import GenericViewSet
from rest_framework import mixins
from rest_framework.response import Response

from django.contrib.auth.models import User


class OCSViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   GenericViewSet):
        

    def create(self, request, *args, **kwargs):
        """
        handles post request, suitable for single and multi creation

        Args:
            request ([dict]): can be dict or list of dicts

        Returns:
            [type]: [description]
        """
        print("CREATE ATTEMPT")
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        return Response(serializer.data)


    def update_instance(self, elem, partial):
        instance = self.model.objects.get(username=elem['username'])
        serializer = self.get_serializer(instance, data=elem, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return serializer


    def put(self, request, *args, **kwargs):
        """
        handles put request, either as an update or partial update

        2 cases : 
            - request is a list : bulk update will be performed
            - request is a dict : single update

        Args:
            request ([type])

        Returns:
            [dict]
        """
        print("UPDATE ATTEMPT")
        if isinstance(request.data, list):
            for elem in request.data:
                partial = kwargs.pop('partial', False)
                try :
                    serializer = self.update_instance(elem, partial)
                except :
                    return Response({"error":"update failed, one or more element could not be updated"})
        else:
            try :
                partial = kwargs.pop('partial', False)
                serializer = self.update_instance(request.data, partial)
            except :
                return Response({"error":"update failed"})

        return Response(serializer.data)
