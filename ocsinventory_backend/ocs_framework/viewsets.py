import logging

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
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

    logger = logging.getLogger("OCSViewSet")

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
            if request.query_params.get("delete"):
                for id in request.data["ids"]:
                    instance = self.model.objects.get(id=id)
                    self.perform_destroy(instance)
            else:
                serializer = self.get_serializer(
                    data=request.data, many=isinstance(request.data, list)
                )
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)
        except Exception as e:
            # serializer.errors may return more details
            return Response(
                {"failed": request.data, "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
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


class RestrictVisibilityViewSet(OCSViewSet):
    """
    Viewset to restrict visibility and modification of objects

    Args:
        OCSViewSet ([ModelViewSet])
    """

    def update(self, request, *args, **kwargs):
        """
        User needs to either be the creator or part of the group
        (if allow_group_modification is enabled) to modify a
        visibility restricted object
        """
        search = self.get_object()
        user = request.user

        # check if user is the creator
        if search.user == user:
            return super().update(request, *args, **kwargs)

        # for group private searches, check if group modification is allowed
        if search.visibility == "private_group" and not search.allow_group_modification:
            return Response(
                {"detail": "You do not have permission to modify this item."},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif (
            search.visibility == "private_group"
            and search.allow_group_modification
            and not search.groups.filter(id__in=user.groups.all())
        ):
            return Response(
                {"detail": "You do not have permission to modify this item."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # for public searches, check if user is the creator
        if search.visibility == "public" and search.user != user:
            return Response(
                {"detail": "You do not have permission to modify this item."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().update(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """
        Return the list of objects that the user can see (public,
        private_personal, private_group)
        """
        user = request.user
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(
            Q(visibility="public") | Q(user=user) | Q(groups__in=user.groups.all())
        ).distinct()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        User needs to be the creator to delete a visibility restricted object
        """
        search = self.get_object()
        user = request.user
        if search.user == user:
            return super().destroy(request, *args, **kwargs)
        return Response(
            {"detail": "You do not have permission to delete this item."},
            status=status.HTTP_403_FORBIDDEN,
        )


class ExpandableFieldsMixin:
    """
    Mixin to dynamically expand nested fields based on the "expand" query parameter.
    
    To use, add an `expandable_fields` dictionary in your serializer's Meta:
    
        expandable_fields = {
            "some_relation": SomeNestedSerializer,
            "other_relation": OtherNestedSerializer,
        }
        
    The mixin will:
      - Expand all fields and childs if expand="*"
      - Expand fields provided in a comma separated list (expand=field1,field2)
      - or return the pks for the relation
      
    """
    def to_representation(self, instance):
        # get default representation
        representation = super().to_representation(instance)
        request = self.context.get("request")
        if not request:
            return representation

        # track depth
        current_depth = self.context.get('expand_depth', 0)
        if current_depth >= 1:
            return representation

        expand_param = request.query_params.get("expand", "")
        expandable_fields = getattr(self.Meta, "expandable_fields", {})

        # expand all fields
        if expand_param == "*":
            for field, serializer_class in expandable_fields.items():
                field_obj = getattr(instance, field, None)
                if field_obj is not None:
                    if field == "assets" or field == "groups":
                        representation[field+"_expand"] = serializer_class(
                            field_obj.filter(id__in=representation[field]), many=True
                        ).data
                    elif getattr(self.fields[field], "many", False):
                        # handle many
                        representation[field] = serializer_class(
                            field_obj.all(), many=True, context={**self.context, 'expand_depth': current_depth}
                        ).data
                    else:
                        representation[field] = serializer_class(
                            field_obj, context={**self.context, 'expand_depth': current_depth}
                        ).data
            return representation

        # parse comma separated fields
        expand_fields = [field.strip() for field in expand_param.split(",") if field.strip()]

        for field, serializer_class in expandable_fields.items():
            if field in expand_fields:
                field_obj = getattr(instance, field, None)
                if field_obj is not None:
                    # handle many
                    if field == "assets" or field == "groups":
                        representation[field+"_expand"] = serializer_class(
                            field_obj.filter(id__in=representation[field]), many=True
                        ).data
                    elif getattr(self.fields[field], "many", False):
                        representation[field] = serializer_class(
                            field_obj.all(), many=True, context={**self.context, 'expand_depth': current_depth}
                        ).data
                    else:
                        representation[field] = serializer_class(
                            field_obj, context={**self.context, 'expand_depth': current_depth}
                        ).data
            else:
                # handle non expanded fields
                field_obj = getattr(instance, field, None)
                if field_obj:
                    if hasattr(field_obj, "all"):
                        representation[field] = [item.pk for item in field_obj.all()]
                    elif hasattr(field_obj, "pk"):
                        representation[field] = field_obj.pk

        return representation
