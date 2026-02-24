import logging

from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from asset.legacy.parsers import LegacyXMLParser
from asset.legacy.renderers import LegacyXMLRenderer
from inventory.field.models import Field
from inventory.section.models import Section
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView


class LegacyView(APIView):
    """
    Allows creation and update of assets's legacy (base and inventory if provided).
    This view is reachable at the /asset/collection/ endpoint.

    POST:
    Create asset and inventory legacy(if provided)
    also perform partial update of asset legacy and inventory legacy(if provided) using
    InventoryBaseSerializer, InventorySectionSerializer, and
    InventoryFieldSerializer
    """

    permission_classes = []

    LOGGER = logging.getLogger(__name__)

    parser_classes = [LegacyXMLParser]
    renderer_classes = [LegacyXMLRenderer]

    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        """
        Perform creation or partial update of asset and inventory legacy. If inventory
        (template_inventory) is provided, we retrieve the related template
        sections and fields and create the corresponding InventorySection and
        InventoryField objects.

        args:
            request: request object
            args: args
            kwargs: kwargs

        returns:
            Response object
        """
        data = request.data
        errors = []
        try:
            self.LOGGER.info(
                "Managing inventory for legacy device %s - %s",
                data["uuid"],
                data["name"],
            )
        except Exception as e:
            self.LOGGER.error("Missing required data: %s", e)
        try:
            if data["query"] == "PROLOG":
                return Response(
                    {
                        "RESPONSE": "SEND",
                        "PROLOG_FREQ": 24,
                        "INVENTORY_ON_STARTUP": 1,
                    },
                    status=200,
                )
            if InventoryBase.objects.filter(uuid=data["uuid"]):
                self.LOGGER.info(
                    "Updating inventory for device %s - %s",
                    data["uuid"],
                    data["name"],
                )
                try:
                    asset_serializer = InventoryBaseSerializer(
                        InventoryBase.objects.get(uuid=data["uuid"]),
                        data=data,
                    )
                    if asset_serializer.is_valid(raise_exception=True):
                        asset_instance = asset_serializer.save()

                except ValidationError as ve:
                    errors.append(f"Error while updating inventory: {ve}")
                    self.LOGGER.error(
                        "Error while updating inventory for device %s - %s: %s",
                        data["uuid"],
                        data["name"],
                        ve,
                    )
                    return Response(
                        {"error": errors},
                        status=400,
                    )
                except Exception as e:
                    self.LOGGER.error("Error while updating inventory for device %s - %s: %s",
                    data["uuid"],
                    data["name"],
                    e
                )
                    return Response(
                        {"error": f"Error while updating inventory: {e}"},
                        status=500,
                    )

                # pre-fetch Sections and Fields
                section_objs = Section.objects.filter(
                    template=asset_instance.template_id
                )
                field_objs = Field.objects.filter(section__in=section_objs)
                section_field_map = {
                    section.name: {
                        field.retrieval_value: field
                        for field in field_objs.filter(section=section)
                    }
                    for section in section_objs
                }

                if "template_inventory" in data:
                    sections_array = data.pop("template_inventory")

                    new_fields = []

                    for (
                        section_name,
                        items,
                    ) in sections_array.items():
                        section_query = section_objs.filter(name=section_name).first()
                        if not section_query:
                            errors.append(
                                f"Section {section_name} not found in template"
                            )
                            continue

                        # delete existing sections for this template section
                        InventorySection.objects.filter(
                            base=asset_instance,
                            template_section=section_query,
                        ).delete()

                        field_map = section_field_map.get(
                            section_name,
                            {},
                        )
                        for item in items:
                            section_instance = InventorySection(
                                base=asset_instance,
                                template_section=section_query,
                            )
                            section_instance.save()

                            for (
                                field_name,
                                field_value,
                            ) in item.items():
                                field_obj = field_map.get(field_name)
                                if not field_obj:
                                    errors.append(
                                        f"Field {field_name} not found in section {section_name}"
                                    )
                                    continue

                                new_field = InventoryField(
                                    inventory_section=section_instance,
                                    template_field=field_obj,
                                    value=field_value,
                                )
                                new_fields.append(new_field)

                    # bulk create fields
                    InventoryField.objects.bulk_create(new_fields)

                if errors:
                    self.LOGGER.error(
                        "Partial update completed with errors for device %s - %s: %s",
                        data["uuid"],
                        data["name"],
                        errors,
                    )
                    return Response(
                        {
                            "Partial update completed with errors for device "
                            f'{data["uuid"]} - {data["name"]}: {str(errors)}'
                        },
                        status=200,
                    )
                else:
                    self.LOGGER.info(
                        "Inventory updated successfully for device %s - %s",
                        data["uuid"],
                        data["name"],
                    )

                return Response(
                    {"message": "Asset legacy and inventory updated successfully"},
                    status=200,
                )
            else:
                self.LOGGER.info("Creating inventory for device %s - %s",
                data["uuid"],
                data["name"],
                )

                try:
                    asset_serializer = InventoryBaseSerializer(data=data)
                    if asset_serializer.is_valid(raise_exception=True):
                        asset_instance = asset_serializer.save()
                        templateId = (
                            asset_instance.template_id
                            if asset_instance.template
                            else None
                        )
                except ValidationError as ve:
                    errors.append(f"Error while creating inventory: {ve}")
                    self.LOGGER.error(
                        "Error while creating inventory for device %s - %s: %s",
                        data["uuid"],
                        data["name"],
                        ve
                    )
                    return Response(
                        {"error": errors},
                        status=400,
                    )

                except Exception as e:
                    self.LOGGER.error("Error while creating inventory for device %s - %s: %s",
                    data["uuid"],
                    data["name"],
                    e
                )
                    return Response(
                        {"error": f"Error while creating inventory: {e}"},
                        status=500,
                    )

                # pre-fetch all Sections and Fields for this template
                section_objs = Section.objects.filter(template=templateId)
                field_objs = Field.objects.filter(section__in=section_objs)
                section_field_map = {
                    section.name: {
                        field.retrieval_value: field
                        for field in field_objs.filter(section=section)
                    }
                    for section in section_objs
                }

                # handle template inventory if present
                if "template_inventory" in data:
                    sections_array = data.pop("template_inventory")

                    fields_to_create = []

                    for section_name, items in sections_array.items():
                        section_obj = section_objs.filter(name=section_name).first()
                        if not section_obj:
                            errors.append(
                                f"No matching section found for {section_name}"
                            )
                            continue

                        field_map = section_field_map.get(
                            section_name,
                            {},
                        )
                        for item in items:
                            section_instance = InventorySection(
                                base=asset_instance,
                                template_section=section_obj,
                            )
                            section_instance.save()

                            for (
                                field_name,
                                field_value,
                            ) in item.items():
                                field_obj = field_map.get(field_name)
                                if not field_obj:
                                    errors.append(
                                        f"No matching legacy field found for {field_name}"
                                        f" in section {section_name}"
                                    )
                                    continue

                                fields_to_create.append(
                                    InventoryField(
                                        inventory_section=section_instance,
                                        template_field=field_obj,
                                        value=field_value,
                                    )
                                )

                    # bulk create sections and fields
                    InventoryField.objects.bulk_create(fields_to_create)

                if errors:
                    self.LOGGER.error(
                        "Errors encountered while creating legacy inventory "
                        "for device %s - %s: %s",
                        data["uuid"],
                        data["name"],
                        errors,
                    )

                    return Response(
                        {
                            "Inventory created with errors for device "
                            f'{data["uuid"]} - {data["name"]}: {str(errors)}'
                        },
                        status=201,
                    )
                else:
                    self.LOGGER.info(
                        "Inventory created successfully for legacy device %s - %s",
                        data["uuid"],
                        data["name"],
                    )

                # successful creation response
                return Response(
                    {"message": "Inventory legacy created successfully"},
                    status=201,
                )
        except KeyError as e:
            missing_key = e.args[0]
            self.LOGGER.error("Missing required data: %s", missing_key)
            return Response(
                f"Missing required data: {missing_key}",
                status=400,
            )
