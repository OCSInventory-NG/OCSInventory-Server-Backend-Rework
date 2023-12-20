from rest_framework.response import Response
import logging

from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from asset.inventory_section.serializers import InventorySectionSerializer
from asset.inventory_field.serializers import InventoryFieldSerializer
from inventory.section.models import Section
from inventory.field.models import Field
from rest_framework.views import APIView


class CollectionView(APIView):
    """
    Allows creation of assets (base and inventory if provided).
    This view is reachable at the /asset/collection/ endpoint.

    POST:
    Create asset and inventory (if provided) using InventoryBaseSerializer,
    InventorySectionSerializer, and InventoryFieldSerializer

    PUT:
    TODO : update asset and inventory (if provided) using
    InventoryBaseSerializer, InventorySectionSerializer, and
    InventoryFieldSerializer
    """

    permission_classes = []

    LOGGER = logging.getLogger(__name__)

    def post(self, request, *args, **kwargs):
        """
        Override post method to create asset and inventory (if provided) using
        InventoryBaseSerializer, InventorySectionSerializer,
        and InventoryFieldSerializer

        args:
            request: request object
            args: args
            kwargs: kwargs

        returns:
            Response object
        """
        data = request.data

        # create Base asset using BaseSerializer
        asset_serializer = InventoryBaseSerializer(data=data)
        if asset_serializer.is_valid():
            asset_instance = asset_serializer.save()
            templateId = (asset_instance.template_id
                          if asset_instance.template else None)
        else:
            return Response(asset_serializer.errors, status=400)

        # handle template inventory if present
        if 'template_inventory' in data:
            sectionsArray = data.pop('template_inventory')

            # loop through sections array
            for section in sectionsArray:
                for name, fields in section.items():
                    # retrieve section ID
                    section_query = Section.objects.filter(name=name,
                                                           template=templateId)
                    if not section_query.exists():
                        continue  # skip if no matching section found
                    sectionId = section_query.first().id

                    # create InventorySection
                    section_serializer = InventorySectionSerializer(
                        data={'base': asset_instance.id,
                              'template_section': sectionId})
                    if section_serializer.is_valid():
                        section_instance = section_serializer.save()
                    else:
                        return Response(section_serializer.errors, status=400)

                    # loop through each field object in fields array
                    for field_object in fields:
                        for field_name, field_value in field_object.items():
                            # retrieve field ID
                            field_query = Field.objects.filter(
                                name=field_name,
                                section=sectionId)
                            if not field_query.exists():
                                continue  # skip if no matching field found
                            fieldId = field_query.first().id

                            # create InventoryField
                            field_serializer = InventoryFieldSerializer(
                                data={'inventory_section': section_instance.id,
                                      'template_field': fieldId,
                                      'value': field_value})
                            if field_serializer.is_valid():
                                field_serializer.save()
                            else:
                                return Response(field_serializer.errors,
                                                status=400)

        # successful creation response
        return Response({'message':
                         'Asset and inventory created successfully'},
                        status=201)

    def put(self, request, *args, **kwargs):
        """
        Perform full update of asset and inventory (if provided) using
        InventoryBaseSerializer, InventorySectionSerializer,
        and InventoryFieldSerializer

        In this specific case, we update the Base asset and overwrite the
        existing inventory (full overwrite), meaning that if a section or
        field is not provided, it will be deleted

        args:
            request: request object
            args: args
            kwargs: kwargs

        returns:
            Response object
        """
        data = request.data

        # retrieve asset ID from uuid
        asset_query = InventoryBase.objects.filter(uuid=data['uuid'])
        if not asset_query.exists():
            return Response({'message': 'Asset not found'}, status=404)

        # update Base asset using BaseSerializer
        asset_serializer = InventoryBaseSerializer(asset_query.first(),
                                                   data=data)
        if asset_serializer.is_valid():
            asset_instance = asset_serializer.save()
            templateId = (asset_instance.template_id
                          if asset_instance.template else None)
        else:
            return Response(asset_serializer.errors, status=400)

        # update inventory
        if 'template_inventory' in data:
            sectionsArray = data.pop('template_inventory')

            # retrieve existing sections
            section_query = InventorySection.objects.filter(
                base=asset_instance.id)
            existing_sections = []
            for section in section_query:
                existing_sections.append(section.id)

            # loop through sections array
            for section in sectionsArray:
                for name, fields in section.items():
                    # retrieve section ID
                    section_query = Section.objects.filter(name=name,
                                                           template=templateId)
                    if not section_query.exists():
                        continue
                    sectionId = section_query.first().id

                    # update or create InventorySection
                    if name in existing_sections:
                        section_serializer = InventorySectionSerializer(
                            Section.objects.get(id=existing_sections[name]),
                            data={'base': asset_instance.id,
                                  'template_section': sectionId})
                    else:
                        section_serializer = InventorySectionSerializer(
                            data={'base': asset_instance.id,
                                  'template_section': sectionId})
                    if section_serializer.is_valid():
                        section_instance = section_serializer.save()
                    else:
                        return Response(section_serializer.errors, status=400)

                    # retrieve existing fields
                    field_query = InventoryField.objects.filter(
                        inventory_section=section_instance.id)
                    existing_fields = []
                    for field in field_query:
                        existing_fields.append(field.id)

                    # loop through each field object in fields array
                    for field_object in fields:
                        for field_name, field_value in field_object.items():
                            # retrieve field ID
                            field_query = Field.objects.filter(
                                name=field_name,
                                section=sectionId)
                            if not field_query.exists():
                                continue
                            fieldId = field_query.first().id

                            # update or create InventoryField
                            if field_name in existing_fields:
                                field_serializer = InventoryFieldSerializer(
                                    InventoryField.objects.get(
                                        id=existing_fields[field_name]),
                                    data={
                                        'inventory_section':
                                        section_instance.id,
                                        'template_field': fieldId,
                                        'value': field_value})
                            else:
                                field_serializer = InventoryFieldSerializer(
                                    data={
                                        'inventory_section':
                                        section_instance.id,
                                        'template_field': fieldId,
                                        'value': field_value})
                            if field_serializer.is_valid():
                                field_serializer.save()
                            else:
                                return Response(field_serializer.errors,
                                                status=400)

                            # remove field from existing fields
                            if field_name in existing_fields:
                                existing_fields.pop(field_name)

                    # remove section from existing sections
                    if name in existing_sections:
                        existing_sections.pop(name)

            # delete remaining sections
            for section in existing_sections:
                InventorySection.objects.get(id=section).delete()

            # delete remaining fields
            for field in existing_fields:
                InventoryField.objects.get(id=field).delete()

        # successful update response
        return Response({'message':
                         'Asset and inventory updated successfully'},
                        status=200)

    def patch(self, request, *args, **kwargs):
        """
        Perform partial update of asset and inventory (if provided) using
        InventoryBaseSerializer, InventorySectionSerializer,
        and InventoryFieldSerializer

        In this specific case, we update the Base asset and update only the
        provided sections and fields (partial overwrite)
        """
        data = request.data

        # retrieve asset ID from uuid
        asset_query = InventoryBase.objects.filter(uuid=data['uuid'])
        if not asset_query.exists():
            return Response({'message': 'Asset not found'}, status=404)

        # update Base asset using BaseSerializer
        asset_serializer = InventoryBaseSerializer(asset_query.first(),
                                                   data=data)
        if asset_serializer.is_valid():
            asset_instance = asset_serializer.save()
            templateId = (asset_instance.template_id
                          if asset_instance.template else None)
        else:
            return Response(asset_serializer.errors, status=400)

        # update inventory
        if 'template_inventory' in data:
            sectionsArray = data.pop('template_inventory')

            # loop through sections array
            for section in sectionsArray:
                for name, fields in section.items():
                    # retrieve section ID
                    section_query = Section.objects.filter(name=name,
                                                           template=templateId)
                    if not section_query.exists():
                        continue
                    sectionId = section_query.first().id

                    # update or create InventorySection
                    # if section exists, update it
                    section_instance = InventorySection.objects.get(
                        template_section=sectionId,
                        base=asset_instance.id
                        )
                    if section_instance:
                        section_serializer = InventorySectionSerializer(
                            section_instance,
                            data={'base': asset_instance.id,
                                  'template_section': sectionId})
                    else:
                        section_serializer = InventorySectionSerializer(
                            data={'base': asset_instance.id,
                                  'template_section': sectionId})
                        if section_serializer.is_valid():
                            section_instance = section_serializer.save()
                        else:
                            return Response(section_serializer.errors,
                                            status=400)

                    # loop through each field object in fields array
                    for field_object in fields:
                        for field_name, field_value in field_object.items():
                            # retrieve field ID
                            field_query = Field.objects.filter(
                                name=field_name,
                                section=sectionId)
                            if not field_query.exists():
                                continue
                            fieldId = field_query.first().id

                            # only updating for the fields
                            # because fields should already exist even if empty
                            field_serializer = InventoryFieldSerializer(
                                InventoryField.objects.get(
                                    template_field=fieldId,
                                    inventory_section=section_instance.id),
                                data={
                                    'inventory_section':
                                    section_instance.id,
                                    'template_field': fieldId,
                                    'value': field_value})
                            if field_serializer.is_valid():
                                field_serializer.save()
                            else:
                                return Response(field_serializer.errors,
                                                status=400)

        # successful update response
        return Response({'message':
                         'Asset and inventory updated successfully'},
                        status=200)
