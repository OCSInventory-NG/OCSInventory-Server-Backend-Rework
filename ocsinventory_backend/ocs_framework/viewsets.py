import logging

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response


class ApiCheckResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class ApiCheckViewSet(viewsets.ModelViewSet):
    permission_classes = []

    @extend_schema(
        description="Health check endpoint, used to verify the API is reachable.",
        responses=ApiCheckResponseSerializer,
    )
    def api_check(self, request, *args, **kwargs):
        return Response(
            {
                "message": "API is online!",
            },
            status=status.HTTP_200_OK,
        )


class OCSViewSet(viewsets.ModelViewSet):
    """
    This class will define the general view behavior for the framework

    Args:
        viewsets ([ModelViewSet])
    """

    # Set default filter
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # Filter on all by default
    filterset_fields = "__all__"

    # This is the default reconciliation id for objets, can overrided
    reconciliation_field = "id"

    ordering_fields = "__all__"
    # default ordering
    ordering = ["id"]

    logger = logging.getLogger("OCSViewSet")

    def create(self, request, *args, **kwargs):
        """
        Handle post request, suitable for single and multi creation

        Args:
            request ([dict]): can be dict or list of dicts

        Returns:
            [type]: [description]
        """
        if request.query_params.get("delete"):
            return self.bulk_destroy(request)

        # 'many' allows multi creation but any error
        # will fail the whole transaction
        try:
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

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def bulk_destroy(self, request):
        """
        Handle POST ?delete=1 with {"ids": [...]}, all or nothing

        Each id goes through the checks of a DELETE on a single object : the
        delete permission, the objects the user can reach, and
        check_destroy_allowed
        """
        self.check_delete_permission(request)

        ids = request.data.get("ids") if isinstance(request.data, dict) else None
        try:
            ids = {int(id) for id in ids} if isinstance(ids, list) else None
        except (TypeError, ValueError):
            ids = None
        if not ids:
            return Response(
                {"failed": request.data, "error": "ids must be a list of object ids"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instances = list(self.get_queryset().filter(id__in=ids))
        missing = ids - {instance.id for instance in instances}
        if missing:
            return Response(
                {"detail": "Not found.", "ids": sorted(missing)},
                status=status.HTTP_404_NOT_FOUND,
            )

        for instance in instances:
            self.check_destroy_allowed(instance)

        with transaction.atomic():
            for instance in instances:
                self.perform_destroy(instance)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def check_delete_permission(self, request):
        """
        A bulk delete travels as a POST, require what a DELETE would
        """
        model = self.get_queryset().model
        for permission in self.get_permissions():
            if isinstance(permission, DjangoModelPermissions):
                required = permission.get_required_permissions("DELETE", model)
                if not request.user.has_perms(required):
                    raise PermissionDenied()

    def check_destroy_allowed(self, instance):
        """
        Hook to refuse the deletion of a reachable object, raise PermissionDenied
        """

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

        # for public and private_personal items, only the creator may modify
        # (already excluded above); anyone else is forbidden
        if search.visibility in ("public", "private_personal") and search.user != user:
            return Response(
                {"detail": "You do not have permission to modify this item."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        """
        Restrict every route, list and detail alike, to the objects the user
        can see (public, private_personal, private_group)
        """
        return super().get_queryset().visible_to(self.request.user)

    def destroy(self, request, *args, **kwargs):
        """
        User needs to be the creator to delete a visibility restricted object
        """
        instance = self.get_object()
        self.check_destroy_allowed(instance)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def check_destroy_allowed(self, instance):
        """Only the creator deletes, single or bulk"""
        if instance.user != self.request.user:
            raise PermissionDenied("You do not have permission to delete this item.")


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
        current_depth = self.context.get("expand_depth", 0)
        # Limit recursion depth if needed
        max_depth = 1
        if current_depth >= max_depth:
            return representation

        expand_param = request.query_params.get("expand", "")
        expandable_fields = getattr(self.Meta, "expandable_fields", {})

        # Determine which fields to expand
        expand_all = expand_param == "*"
        explicit_expand_fields = set(
            field.strip() for field in expand_param.split(",") if field.strip()
        )

        # Get model metadata once
        model_meta = instance._meta

        for field, serializer_class in expandable_fields.items():
            should_expand = expand_all or field in explicit_expand_fields

            if should_expand:
                try:
                    field_obj = getattr(instance, field, None)
                    if field_obj is not None:
                        model_field = model_meta.get_field(field)
                        new_context = {
                            **self.context,
                            "expand_depth": current_depth + 1,
                        }

                        # Handle ManyToMany and Reverse ForeignKey/OneToOne
                        if model_field.many_to_many or model_field.one_to_many:
                            representation[field] = serializer_class(
                                field_obj.all(), many=True, context=new_context
                            ).data
                        # Handle ForeignKey and OneToOne
                        elif model_field.many_to_one or model_field.one_to_one:
                            representation[field] = serializer_class(
                                field_obj, context=new_context
                            ).data
                except Exception as e:
                    # Handle cases where getattr fails
                    # or field doesn't exist as expected
                    self.logger.error(f"Error expanding field '{field}': {e}")
                    if field in representation:
                        del representation[field]

            else:
                # Handle non-expanded fields (represent as PKs)
                try:
                    field_obj = getattr(instance, field, None)
                    if field_obj is not None:
                        model_field = model_meta.get_field(field)
                        if model_field.many_to_many or model_field.one_to_many:
                            # Ensure it's iterable before list comprehension
                            if hasattr(field_obj, "all"):
                                representation[field] = [
                                    item.pk for item in field_obj.all()
                                ]
                            else:
                                representation[field] = []
                        elif model_field.many_to_one or model_field.one_to_one:
                            representation[field] = field_obj.pk

                except Exception as e:
                    self.logger.error(f"Error getting PK for field '{field}': {e}")
                    if field in representation:
                        del representation[field]

        return representation
