from django.db.models import F
from inventory.field.models import Field
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class FieldSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Field
        fields = [
            "id",
            "name",
            "order",
            "retrieval_value",
            "override_target",
            "new_target",
            "retrieval_method",
            "retrieval_output",
            "section",
            "options",
        ]
        expandable_fields = {}

    def custom_validate(self, data):
        """
        Perform custom validation on the Field data.
        """
        if (
            Field.objects.filter(section=data["section"])
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            # adjust orders if there's a conflict
            # if the current order is being updated to a higher order
            if self.instance and data["order"] < self.instance.order:

                Field.objects.filter(
                    section=data["section"],
                    order__lt=self.instance.order,
                    order__gte=data["order"],
                ).exclude(pk=self.instance.pk if self.instance else None).update(
                    order=F("order") + 1
                )

            # if the current order is being updated to a lower order
            elif self.instance and data["order"] > self.instance.order:
                Field.objects.filter(
                    section=data["section"],
                    order__lte=data["order"],
                    order__gt=self.instance.order,
                ).exclude(pk=self.instance.pk if self.instance else None).update(
                    order=F("order") - 1
                )
            # adjust orders of existing configs
            else:
                Field.objects.filter(
                    section=data["section"], order__gte=data["order"]
                ).update(order=F("order") + 1)
        return data

    def create(self, validated_data):
        """
        Overriding the create method to manage field order.
        """
        validated_data["order"] = (
            Field.objects.filter(section=validated_data["section"]).count() + 1
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Overriding the update method
        """
        # custom validation
        validated_data = self.custom_validate(validated_data)
        return super().update(instance, validated_data)


class FieldExportSerializer(ModelSerializer):
    """
    Export serializer for Field, ids and fk relations are not included
    """

    class Meta:
        model = Field
        fields = ["name", "retrieval_value", "override_target", "new_target",
                  "retrieval_method", "retrieval_output", "options"]
