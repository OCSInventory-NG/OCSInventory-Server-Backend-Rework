from deployment.package.models import Package
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class PackageSerializer(ExpandableSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Package
        fields = [
            "id",
            "name",
            "description",
            "date_created",
            "target_os",
            "actions_list",
            "result",
        ]

        expandable_fields = {
            "actions_list": {
                "serializer": "deployment.action.serializers.ActionSerializer",
                "many": True,
                "required": False
            },
            "result": {
                "serializer": "deployment.result.serializers.ResultSerializer",
                "many": True,
                "required": False
            }
        }

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        # any actions?
        if "actions" in validated_data.keys():
            actions = validated_data.pop("actions")
        if "result" in validated_data.keys():
            result = validated_data.pop("result")

        # keep the parent created
        parent = super().create(validated_data)
        # create actions
        if "actions" in validated_data.keys():
            for action in actions:
                action["package"] = parent
            # actions serializer
            self.fields["actions"].create(actions)

        # create result
        if "result" in validated_data.keys():
            for res in result:
                res["package"] = parent
            # result serializer
            self.fields["result"].create(result)

        return parent
