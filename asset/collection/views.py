import logging

from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_section.models import InventorySection
from asset.inventory_field.models import InventoryField
from django.core.exceptions import ObjectDoesNotExist
from inventory.field.models import Field
from inventory.section.models import Section
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView


class CollectionView(APIView):
    """
    Allows creation and update of assets (base and inventory if provided).
    This view is reachable at the /asset/collection/ endpoint.

    POST:
    Create asset and inventory (if provided) using InventoryBaseSerializer,
    InventorySectionSerializer, and InventoryFieldSerializer

    PUT:
    Update asset and inventory (if provided) using
    InventoryBaseSerializer, InventorySectionSerializer, and
    InventoryFieldSerializer

    PATCH:
    Perform partial update of asset and inventory (if provided) using
    InventoryBaseSerializer, InventorySectionSerializer, and
    InventoryFieldSerializer
    """

    permission_classes = []

    LOGGER = logging.getLogger(__name__)

    def post(self, request, *args, **kwargs):
        """
        Perform creation of asset and inventory. If inventory
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
        self.LOGGER.info("Creating inventory for device %s - %s", data["uuid"], data["name"])

        try:
            asset_serializer = InventoryBaseSerializer(data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
                templateId = (
                    asset_instance.template_id if asset_instance.template else None
                )
        except ValidationError as ve:
            errors.append(f"Error creating asset: {ve}")
            self.LOGGER.error(f"Error creating asset: {ve}")
            return Response({"error": errors}, status=400)
        except Exception as e:
            self.LOGGER.error(f"Error creating asset: {e}")
            return Response({"error": f"Error creating asset: {e}"}, status=500)

        # pre-fetch all Sections and Fields for this template
        section_objs = Section.objects.filter(template=templateId)
        field_objs = Field.objects.filter(section__in=section_objs)
        section_field_map = {section.name:
                             {field.name: field for field in field_objs.filter(
                                 section=section)} for section in section_objs}

        # handle template inventory if present
        if "template_inventory" in data:
            sections_array = data.pop("template_inventory")

            sections_to_create = []
            fields_to_create = []

            for section_name, items in sections_array.items():
                section_obj = section_objs.filter(name=section_name).first()
                if not section_obj:
                    errors.append(f"No matching section found for {section_name}")
                    continue

                field_map = section_field_map.get(section_name, {})
                for item in items:
                    section_instance = InventorySection(base=asset_instance,
                                                        template_section=section_obj)
                    sections_to_create.append(section_instance)

                    for field_name, field_value in item.items():
                        field_obj = field_map.get(field_name)
                        if not field_obj:
                            errors.append(f"No matching field found for {field_name}"
                                          f" in section {section_name}")
                            continue

                        fields_to_create.append(InventoryField(
                            inventory_section=section_instance,
                            template_field=field_obj,
                            value=field_value
                        ))

            # bulk create sections and fields
            InventorySection.objects.bulk_create(sections_to_create)
            InventoryField.objects.bulk_create(fields_to_create)

        if errors:
            self.LOGGER.error(
                "Encountered errors while creating inventory " "for device %s - %s: %s",
                data["uuid"],
                data["name"],
                errors,
            )

            return Response(
                {
                    f"Inventory created but errors were encountered "
                    f'while creating device {data["uuid"]} - '
                    f'{data["name"]}: {str(errors)}'
                },
                status=201,
            )
        else:
            self.LOGGER.info(
                "Inventory created successfully for device %s - %s"
                " sending response back to client",
                data["uuid"],
                data["name"],
            )

        # successful creation response
        return Response({"message": "Inventory created successfully"}, status=201)

    def put(self, request):
        """
        Perform update of asset and inventory.
        In this specific case, we update the Base asset and overwrite the
        existing inventory (full overwrite), meaning that if a section or
        field is not provided, it will be deleted of the existing inventory.

        NB: if multiple items are received within a section, these items will
        be added as sections objects, meaning multiple sections with the same
        template_section will be created for the same asset.

        args:
            request: request object

        returns:
            Response object
        """
        data = request.data
        errors = []

        self.LOGGER.info("Updating inventory for device %s - %s", data["uuid"],
                         data["name"])

        try:
            # retrieve asset from UUID
            asset_query = InventoryBase.objects.get(uuid=data["uuid"])
        except ObjectDoesNotExist:
            self.LOGGER.error("Asset not found")
            return Response({"error": "Asset not found"}, status=404)
        except Exception as e:
            self.LOGGER.error(f"Error retrieving asset: {e}")
            return Response({"error": f"Error retrieving asset: {e}"}, status=500)

        try:
            # update asset
            asset_serializer = InventoryBaseSerializer(asset_query, data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
        except ValidationError as ve:
            self.LOGGER.error(f"Error updating asset: {ve}")
            return Response({"error": str(ve)}, status=400)
        except Exception as e:
            self.LOGGER.error(f"Error updating asset: {e}")
            return Response({"error": f"Error updating asset: {e}"}, status=500)

        section_objs = Section.objects.filter(template=asset_instance.template_id)
        field_objs = Field.objects.filter(section__in=section_objs)
        section_field_map = {section.name:
                             {field.name: field for field in field_objs.filter(
                                 section=section)} for section in section_objs}

        # handle template inventory if present
        if "template_inventory" in data:
            sections_array = data.pop("template_inventory")

            # delete existing sections and fields
            InventorySection.objects.filter(base=asset_instance).delete()

            sections_to_create = []
            fields_to_create = []

            for section_name, items in sections_array.items():
                section_obj = section_objs.filter(name=section_name).first()
                if not section_obj:
                    errors.append(f"No matching section found for {section_name}")
                    continue

                field_map = section_field_map.get(section_name, {})
                for item in items:
                    section_instance = InventorySection(base=asset_instance,
                                                        template_section=section_obj)
                    sections_to_create.append(section_instance)

                    for field_name, field_value in item.items():
                        field_obj = field_map.get(field_name)
                        if not field_obj:
                            errors.append(f"No matching field found for {field_name}"
                                          f" in section {section_name}")
                            continue

                        fields_to_create.append(InventoryField(
                            inventory_section=section_instance,
                            template_field=field_obj,
                            value=field_value
                        ))

            # bulk create sections and fields
            InventorySection.objects.bulk_create(sections_to_create)
            InventoryField.objects.bulk_create(fields_to_create)
        if errors:
            self.LOGGER.error(
                "Update succeeded but errors were encountered "
                "while updating device %s - %s: %s",
                data["uuid"],
                data["name"],
                errors,
            )
            return Response(
                {
                    "Update succeeded but errors were encountered "
                    f'while updating device {data["uuid"]} - '
                    f'{data["name"]}: {str(errors)}'
                },
                status=200,
            )
        else:
            self.LOGGER.info(
                "Inventory updated successfully for device %s - %s"
                " sending response back to client",
                data["uuid"],
                data["name"],
            )

        return Response({"message": "Inventory updated successfully"}, status=200)

    def patch(self, request, *args, **kwargs):
        """
        Perform partial update of asset and inventory.
        In this specific case, we update the Base asset and update only the
        provided sections and fields (partial overwrite)

        NB : if multiple items are received within a section, these items will
        be added as sections objects, meaning multiple sections with the same
        template_section will be created for the same asset.
        """
        data = request.data
        errors = []

        self.LOGGER.info("Updating inventory for device %s - %s", data["uuid"], data["name"])

        try:
            # retrieve asset from UUID
            asset_query = InventoryBase.objects.get(uuid=data["uuid"])
        except ObjectDoesNotExist:
            self.LOGGER.error("Asset not found")
            return Response({"error": "Asset not found"}, status=404)
        except Exception as e:
            self.LOGGER.error(f"Error retrieving asset: {e}")
            return Response({"error": f"Error retrieving asset: {e}"}, status=500)

        try:
            # update asset
            asset_serializer = InventoryBaseSerializer(asset_query, data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
        except ValidationError as ve:
            self.LOGGER.error(f"Error updating asset: {ve}")
            return Response({"error": str(ve)}, status=400)
        except Exception as e:
            self.LOGGER.error(f"Error updating asset: {e}")
            return Response({"error": f"Error updating asset: {e}"}, status=500)

        # pre-fetch Sections and Fields
        section_objs = Section.objects.filter(template=asset_instance.template_id)
        field_objs = Field.objects.filter(section__in=section_objs)
        section_field_map = {section.name: {field.name: field for field in field_objs.filter(section=section)} for section in section_objs}

        if "template_inventory" in data:
            sections_array = data.pop("template_inventory")

            new_sections = []
            new_fields = []

            for section_name, items in sections_array.items():
                section_query = section_objs.filter(name=section_name).first()
                if not section_query:
                    errors.append(f"Section {section_name} not found in template")
                    continue

                # delete existing sections for this template section
                InventorySection.objects.filter(base=asset_instance,
                                                template_section=section_query).delete()

                field_map = section_field_map.get(section_name, {})
                for item in items:
                    section_instance = InventorySection(base=asset_instance,
                                                        template_section=section_query)
                    new_sections.append(section_instance)

                    for field_name, field_value in item.items():
                        field_obj = field_map.get(field_name)
                        if not field_obj:
                            errors.append(f"Field {field_name} not found"
                                          f" in section {section_name}")
                            continue

                        new_field = InventoryField(
                            inventory_section=section_instance,
                            template_field=field_obj,
                            value=field_value
                        )
                        new_fields.append(new_field)

            # bulk create sections and fields
            InventorySection.objects.bulk_create(new_sections)
            InventoryField.objects.bulk_create(new_fields)

        if errors:
            self.LOGGER.error(
                "Partial update succeeded but errors were "
                "encountered while updating device %s - %s: %s",
                data["uuid"],
                data["name"],
                errors,
            )
            return Response(
                {
                    "Partial update succeeded but errors were "
                    f"encountered while updating device "
                    f'{data["uuid"]} - {data["name"]}: {str(errors)}'
                },
                status=200,
            )
        else:
            self.LOGGER.info(
                "Inventory updated successfully for device %s - %s"
                " sending response back to client",
                data["uuid"],
                data["name"],
            )

        return Response(
            {"message": "Asset and inventory updated successfully"}, status=200
        )