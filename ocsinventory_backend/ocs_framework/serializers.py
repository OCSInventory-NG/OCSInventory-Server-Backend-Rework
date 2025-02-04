from django.utils.module_loading import import_string
from rest_framework import serializers


class ExpandableSerializer(serializers.ModelSerializer):
    """
    Supports surface level (depth:1) field expansion via URL parameter
    Nested serializers will not expand their own relationships to prevent deep nesting

    Usage in the child serializer:
        class Meta:
            expandable_fields = {
                'related_field': 'path.to.RelatedSerializer',
                # or with additional configuration:
                'related_field': {
                    'serializer': 'path.to.RelatedSerializer',
                    'many': True,
                    'required': False
                }
            }
    """

    def __init__(self, *args, is_nested=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.expanded_fields = set()

        # process expansion if this isn't a nested serializer
        if not is_nested:
            self.process_expandable_fields()
            self._process_field_configurations()

    def process_expandable_fields(self):
        """
        Process which fields should be expanded based on the request parameters
        """
        # check if any expandable fields defined
        if not hasattr(self.Meta, "expandable_fields"):
            return

        request = self.context.get("request")
        # If no request in context (e.g., during POST), skip expansion
        if not request:
            return

        expand_param = request.query_params.get("expand", "")

        # if expand=* include all expandable fields
        if expand_param == "*":
            self.expanded_fields = set(self.Meta.expandable_fields.keys())
            return

        # or comma separated list of fields
        requested_fields = expand_param.split(",")

        # including only the fields that are defined in the expandable_fields
        # of the child serializer
        for field in requested_fields:
            field = field.strip()
            if field and field in self.Meta.expandable_fields:
                self.expanded_fields.add(field)

    def _process_field_configurations(self):
        """
        Process field configurations and set up serializer fields
        """
        if not hasattr(self.Meta, "expandable_fields"):
            return

        for field_name, field_config in self.Meta.expandable_fields.items():
            # config
            if isinstance(field_config, str):
                serializer_class = import_string(field_config)
                many = False
                required = True
            elif isinstance(field_config, dict):
                serializer_class = import_string(field_config['serializer'])
                many = field_config.get('many', False)
                required = field_config.get('required', True)
            else:
                raise ValueError(
                    f"Invalid expandable_fields configuration for {field_name}. "
                    "Must be either a string or a dictionary."
                )

            # is_nested=True prevents recursion
            self.fields[field_name] = serializer_class(
                many=many,
                required=required,
                is_nested=True,
                context=self.context
            )

    def get_serializer_class(self, field_name):
        """
        Get the serializer class and configuration for an expandable field
        """
        field_config = self.Meta.expandable_fields[field_name]

        if isinstance(field_config, str):
            return import_string(field_config), False
        elif isinstance(field_config, dict):
            return import_string(field_config['serializer']), field_config.get('many', False)

        raise ValueError(
            f"Invalid expandable_fields configuration for {field_name}. "
            "Must be either a string or a dictionary."
        )

    def to_representation(self, instance):
        """
        Convert the object instance into json format
        """
        data = super().to_representation(instance)

        # process expanded fields
        for field_name in self.expanded_fields:
            if field_name not in self.Meta.expandable_fields:
                continue

            # get related instance
            related_data = getattr(instance, field_name)
            if related_data is None:
                continue

            serializer_class, many = self.get_serializer_class(field_name)

            # mtm or reverse fk
            if hasattr(related_data, "all") or many:
                serializer = serializer_class(
                    related_data.all() if hasattr(related_data, "all") else related_data,
                    many=True,
                    context=self.context,
                    is_nested=True
                )
            # fk
            else:
                serializer = serializer_class(
                    related_data,
                    context=self.context,
                    is_nested=True
                )

            # replace field with serialized data
            data[field_name] = serializer.data

        return data
