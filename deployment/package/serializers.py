from deployment.action.serializers import ActionSerializer
from deployment.package.models import Package
from deployment.result.serializers import ResultSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class PackageSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serializer class provides the API representation
    """

    actions_list = ActionSerializer(many=True, read_only=False)
    result = ResultSerializer(many=True, read_only=False)

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
            "actions_list": ActionSerializer,
            "result": ResultSerializer,
        }

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        # any actions?
        if "actions_list" in validated_data.keys():
            actions = validated_data.pop("actions_list")
        if "result" in validated_data.keys():
            result = validated_data.pop("result")

        # keep the parent created
        parent = super().create(validated_data)
        # create actions
        if actions:
            for action in actions:
                action["package"] = parent
            # actions serializer
            self.fields["actions_list"].create(actions)

        # create result
        if result:
            for res in result:
                res["package"] = parent
            # result serializer
            self.fields["result"].create(result)

        return parent
