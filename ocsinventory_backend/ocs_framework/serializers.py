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
        
        # get expandable fields configuration
        self.expandable_fields = self.config_expandable_fields()

        request = self.context.get("request")

        # nested serializer for creation/update
        if request and request.method in ("POST", "PUT", "PATCH") and not is_nested:
            self.expanded_fields = set(self.Meta.expandable_fields.keys())
            self.process_field_configurations()
        # nested serializer for read
        elif not is_nested and request and request.method == "GET":
            self.process_expandable_fields()
            self.process_field_configurations()

    def config_expandable_fields(self):
        """
        Retrieves the expandable fields from the Meta class but does not
        instantiate the serializer class yet.   
        """
        if not hasattr(self.Meta, "expandable_fields"):
            return
        
        expandable_fields = {}

        for field_name, field_config in self.Meta.expandable_fields.items():
            # config
            if isinstance(field_config, str):
                expandable_fields[field_name] = {
                    'serializer': import_string(field_config),
                    'many': False,
                    'required': True
                }
            elif isinstance(field_config, dict):
                expandable_fields[field_name] = {
                    'serializer': import_string(field_config['serializer']),
                    'many': field_config.get('many', False),
                    'required': field_config.get('required', True)
                }
            else:
                raise ValueError(
                    f"Invalid expandable_fields configuration for {field_name}. "
                    "Must be either a string or a dictionary."
                )

        return expandable_fields

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
        
        if not expand_param:
            return

        # or comma separated list of fields
        requested_fields = expand_param.split(",")

        if requested_fields:
            # including only the fields that are defined in the expandable_fields
            # of the child serializer
            for field in requested_fields:
                field = field.strip()
                if field and field in self.expandable_fields:
                    self.expanded_fields.add(field)

    def process_field_configurations(self):
        """
        Process field configurations and set up serializer fields
        """
        if not self.expanded_fields:
            return

        # is_nested=True prevents recursion
        for field_name in self.expanded_fields:
            self.fields[field_name] = self.expandable_fields[field_name]['serializer'](
                many=self.expandable_fields[field_name]['many'],
                required=self.expandable_fields[field_name]['required'],
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
