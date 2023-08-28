from django.core.exceptions import FieldError, ObjectDoesNotExist
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.response import Response


class OCSViewSet(viewsets.ModelViewSet):
    """
    This class will define the general view behavior for the framework

    Args:
        viewsets ([ModelViewSet])
    """

    # Set default filter
    filter_backends = [DjangoFilterBackend]

    # Filter on all by default
    filterset_fields = "__all__"

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
                data=request.data, many=isinstance(request.data, list)
            )
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        except (APIException, FieldError, ObjectDoesNotExist):
            # serializer.errors may return more details
            return Response(
                {"failed": request.data}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"success": "200"}, status=status.HTTP_200_OK)

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
        kwargs["partial"] = True
        return self.put(request, *args, **kwargs)


