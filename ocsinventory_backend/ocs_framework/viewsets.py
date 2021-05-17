from django.core.exceptions import FieldError, ObjectDoesNotExist
from rest_framework import views, viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException


class OCSViewSet(viewsets.ModelViewSet):
    """
    This class will define the general view behavior for the framework

    Args:
        viewsets ([ModelViewSet])
    """

    # This is the default reconciliation id for objets, can overrided
    reconciliation_field = "id"

    def create(self, request, *args, **kwargs):
        """
        Handle post request, suitable for single and multi creation

        Args:
            request ([dict]): can be dict or list of dicts

        Returns:
            [type]: [description]
        """
        # 'many' allows multi creation but any error
        # will fail the whole transaction
        try:
            serializer = self.get_serializer(
                data=request.data, many=isinstance(request.data, list))
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        except (APIException, FieldError, ObjectDoesNotExist):
            # serializer.errors may return more details
            return Response({'failed': request.data}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': '200'}, status=status.HTTP_200_OK)

    def get_reconciliation_filter(self, elem):
        """
        Get the reconciliation filter depending on the reconciliation_field

        Args:
            elem ([dict]): update_instance elem list
        """
        return {self.reconciliation_field: elem[self.reconciliation_field]}

    def update_instance(self, elem, partial):
        """
        Update (may be partial) instance

        Args:
            elem ([type]): [description]
            partial ([type]): [description]

        Returns:
            [type]: [description]
        """
        filters = self.get_reconciliation_filter(elem)
        instance = self.model.objects.filter(**filters)[0]
        serializer = self.get_serializer(instance, data=elem, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        """
        Handle incoming patch request, will redirect to put method

        Args:
            request ([type]): [description]

        Returns:
            [type]: [description]
        """
        kwargs['partial'] = True
        return self.put(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """
        Handle put request, either as an update or partial update

        2 cases :
            - request is a list : bulk update will be performed
            - request is a dict : single update

        Args:
            request ([type])

        Returns:
            [dict] :
                - success : all updates were successful
                - partial success : some updates have failed, see attached objects
                - failed : total failure, see attached failing objects
        """
        partial = kwargs.pop('partial', False)
        success = []
        failed = []
        if isinstance(request.data, list):
            for elem in request.data:
                try:
                    self.update_instance(elem, partial)
                    success += [elem]
                except (APIException, FieldError, KeyError):
                    failed += [elem]

            if not failed:
                return Response({'success': '200'}, status=status.HTTP_200_OK)
            if failed and success:
                return Response({'partial success': failed}, status=status.HTTP_200_OK)

            return Response({'failed': failed}, status=status.HTTP_400_BAD_REQUEST)
        try:
            self.update_instance(request.data, partial)
        except (APIException, FieldError):
            return Response({'failed': request.data}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': '200'}, status=status.HTTP_200_OK)
