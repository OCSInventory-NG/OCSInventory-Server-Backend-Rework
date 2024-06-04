from rest_framework import serializers
from deployment.package.models import Package
from deployment.action.serializers import ActionSerializer
from deployment.result.serializers import ResultSerializer


class PackageSerializer(serializers.ModelSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ModelSerializer])
    """

    actions_list = ActionSerializer(many=True, required=False)
    result = ResultSerializer(many=True, required=False)

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
