from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from accountinfo.serializers import AccountinfoDataSerializer
from asset.inventory_base.models import InventoryBase
from inventory.template.serializers import TemplateSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class InventoryBaseSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    Serializer class for Base
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventoryBase
        fields = [
            "id",
            "name",
            "description",
            "serial",
            "osname",
            "osversion",
            "uuid",
            "srcip",
            "srcmac",
            "domain",
            "agent",
            "template",
            "last_update",
            "is_template_forced",
        ]

        expandable_fields = {
            "template": TemplateSerializer,
        }
        extra_kwargs = {"last_update": {"read_only": True}}
        http_method_names = ["get", "post", "patch", "delete"]

    def to_representation(self, instance):
        """
        Customize the representation to include additional fields
        based on the 'accountinfo' URL parameter.
        """
        representation = super().to_representation(instance)

        request = self.context.get("request")
        accountinfo = None

        if request is not None:
            accountinfo = request.query_params.get("accountinfo")

        if not (accountinfo and accountinfo.lower() == "true"):
            return representation

        # get the accountinfo data first return if not found
        data = AccountinfoData.objects.filter(object_id=representation["id"]).first()
        if not data:
            return representation

        # get serialized data
        serialized_data = AccountinfoDataSerializer(data).data
        accountdata = serialized_data["accountdata"]

        if not accountdata:
            return representation

        # get config and value records based on accountdata
        config_ids = [int(key) for key in accountdata.keys()]
        configs = AccountinfoConfig.objects.filter(id__in=config_ids)
        config_mapping = {str(config.id): config.name for config in configs}

        # collect value ids
        value_ids = []
        for value in accountdata.values():
            if isinstance(value, list):
                value_ids.extend(int(val) for val in value)

        values_mapping = {}
        if value_ids:
            values = AccountinfoValue.objects.filter(id__in=value_ids)
            values_mapping = {str(value.id): value.value for value in values}

        # using a specific format for the accountinfo data (frontend requirement)
        account_data = {}
        for key, value in accountdata.items():
            field_name = config_mapping.get(key, key)
            # select
            if isinstance(value, dict):
                account_data[field_name] = value["text"]
            # checkboxes
            elif isinstance(value, list):
                transformed_values = []
                for val in value:
                    transformed_values.append(values_mapping.get(str(val), val))
                account_data[field_name] = ", ".join(transformed_values)
            # text
            else:
                account_data[field_name] = value

        representation["accountinfo"] = account_data
        return representation

    def validate(self, attrs):
        """
        Validate the template field to ensure it has not changed
        when updating an existing InventoryBase instance.
        """

        old_template = getattr(self.instance, 'template').id
        new_template = attrs.get('template', old_template).id

        if old_template != new_template:
            # TODO: Trouver un moyen de faire correspondre les ids des sections avec les ids des templates
            pass

        return attrs