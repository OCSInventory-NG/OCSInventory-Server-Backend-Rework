from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
import logging

from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_section.models import InventorySection
from asset.inventory_section.serializers import InventorySectionSerializer
from asset.inventory_field.serializers import InventoryFieldSerializer
from inventory.section.models import Section
from inventory.field.models import Field
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

        # storing errors
        errors = []

        self.LOGGER.info('Creating inventory for device %s - %s',
                         data['uuid'], data['name'])

        # create Base asset using BaseSerializer
        try:
            asset_serializer = InventoryBaseSerializer(data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
                templateId = (asset_instance.template_id
                              if asset_instance.template else None)
        except ValidationError as ve:
            errors.append(f'Error creating asset: {ve}')
            self.LOGGER.error(f'Error creating asset: {ve}')
            return Response({'error': errors}, status=400)
        except Exception as e:
            # we return a 400 error if the asset could not be created
            self.LOGGER.error(f'Error creating asset: {e}')
            return Response({'error': f'Error creating asset: {e}'},
                            status=500)

        # handle template inventory if present
        if 'template_inventory' in data:
            sectionsArray = data.pop('template_inventory')

            # loop through sections array
            for name, fields in sectionsArray.items():
                # retrieve section ID
                try:
                    section_query = Section.objects.get(name=name,
                                                        template=templateId
                                                        )
                    sectionId = section_query.id
                except ObjectDoesNotExist:
                    errors.append(f'No matching section found for {name}')
                    continue
                except Exception as e:
                    errors.append(f'Error retrieving section {name}: {e}')
                    continue

                # loop through each field object in fields array
                for field_object in fields:
                    try:
                        # create InventorySection
                        section_serializer = InventorySectionSerializer(
                            data={'base': asset_instance.id,
                                  'template_section': sectionId})
                        if section_serializer.is_valid(
                                raise_exception=True):
                            section_instance = section_serializer.save()
                    except ValidationError as ve:
                        errors.append("Error creating "
                                      f"section {name}: {str(ve)}")
                        continue
                    except Exception as e:
                        errors.append(f'Error creating section {name}: {e}')
                        continue

                    for field_name, field_value in field_object.items():
                        try:
                            # retrieve field ID
                            field_query = Field.objects.get(
                                                    name=field_name,
                                                    section=sectionId
                                                    )
                            fieldId = field_query.id

                            # create InventoryField
                            field_serializer = InventoryFieldSerializer(
                                data={'inventory_section':
                                      section_instance.id,
                                      'template_field': fieldId,
                                      'value': field_value})
                            if field_serializer.is_valid(
                                    raise_exception=True):
                                field_serializer.save()
                        except ObjectDoesNotExist:
                            errors.append(
                                f'No matching field found for {field_name}'
                                )
                            continue
                        except ValidationError as ve:
                            errors.append('Error creating '
                                          f'field {name} '
                                          f'- {field_value}: {str(ve)}')
                            continue
                        except Exception as e:
                            errors.append('Error creating '
                                          f'field {name} - {field_value}: {e}')
                            continue

        # check if there were any errors
        if errors:
            self.LOGGER.error('Encountered errors while creating inventory '
                              'for device %s - %s: %s', data['uuid'],
                              data['name'], errors)

            return Response({'errors': errors}, status=200)
        else:
            self.LOGGER.info(
                            'Inventory created successfully for device %s - %s'
                            ' sending response back to client', data['uuid'],
                            data['name'])

        # successful creation response
        return Response(
            {'message': 'Inventory created successfully'},
            status=201)

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

        # storing errors
        errors = []

        self.LOGGER.info('Updating inventory for device %s - %s',
                         data['uuid'], data['name'])

        try:
            # retrieve asset from UUID
            asset_query = InventoryBase.objects.get(uuid=data['uuid'])
        except ObjectDoesNotExist:
            self.LOGGER.error('Asset not found')
            return Response({'error': 'Asset not found'}, status=404)
        except Exception as e:
            self.LOGGER.error(f'Error retrieving asset: {e}')
            return Response({'error': f'Error retrieving asset: {e}'},
                            status=500)

        try:
            # update asset
            asset_serializer = InventoryBaseSerializer(asset_query, data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
        except ValidationError as ve:
            self.LOGGER.error(f'Error updating asset: {ve}')
            return Response({'error': str(ve)}, status=400)
        except Exception as e:
            self.LOGGER.error(f'Error updating asset: {e}')
            return Response({'error': f'Error updating asset: {e}'},
                            status=500)

        if 'template_inventory' in data:
            sectionsArray = data.pop('template_inventory')

            try:
                # delete existing sections
                InventorySection.objects.filter(
                                                base=asset_instance.id
                                                ).delete()
            except Exception as e:
                errors.append(f'Error deleting existing sections: {e}')

            for name, fields in sectionsArray.items():
                try:
                    # retrieve section ID
                    section_query = Section.objects.get(
                                    name=name,
                                    template=asset_instance.template_id)
                except ObjectDoesNotExist:
                    errors.append(f'Section {name} not found')
                    continue
                except Exception as e:
                    errors.append(f'Error retrieving section {name}: {e}')
                    continue

                # loop through each field object in fields array
                for field_object in fields:
                    try:
                        # create InventorySection
                        section_serializer = InventorySectionSerializer(
                            data={'base': asset_instance.id,
                                  'template_section': section_query.id})
                        if section_serializer.is_valid(raise_exception=True):
                            section_instance = section_serializer.save()
                    except ValidationError as ve:
                        errors.append('Error creating '
                                      f'section {name}: {str(ve)}')
                        continue
                    except Exception as e:
                        errors.append(f'Error creating section {name}: {e}')
                        continue

                    for field_name, field_value in field_object.items():
                        try:
                            # retrieve field ID
                            field_query = Field.objects.get(
                                                name=field_name,
                                                section=section_query.id)
                        except ObjectDoesNotExist:
                            errors.append(
                                f'Field {field_name} '
                                f'not found in section {name}')
                            continue
                        except Exception as e:
                            errors.append(
                                f'Error retrieving field {field_name} '
                                f'in section {name}: {e}'
                                )
                            continue

                        try:
                            # create InventoryField
                            field_serializer = InventoryFieldSerializer(
                                data={'inventory_section':
                                      section_instance.id,
                                      'template_field': field_query.id,
                                      'value': field_value})
                            if field_serializer.is_valid(
                                    raise_exception=True):
                                field_serializer.save()
                        except ValidationError as ve:
                            errors.append(f'Error creating field {name} '
                                          f'- {field_name} : {str(ve)}')
                            continue
                        except Exception as e:
                            errors.append(f'Error creating '
                                          f'field {name} - {field_name}: {e}')
                            continue

        if errors:
            self.LOGGER.error('Update succeeded but errors were encountered '
                              'while updating device %s - %s: %s',
                              data['uuid'], data['name'], errors)
            return Response({'Update succeeded but errors were encountered '
                             'while updating device %s - %s: %s',
                             data['uuid'], data['name'], errors},
                            status=200)
        else:
            self.LOGGER.info(
                'Inventory updated successfully for device %s - %s'
                ' sending response back to client', data['uuid'],
                data['name'])

        return Response({'message': 'Inventory updated successfully'},
                        status=200)

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

        # storing errors
        errors = []

        self.LOGGER.info('Updating inventory for device %s - %s',
                         data['uuid'], data['name'])

        try:
            # retrieve asset from UUID
            asset_query = InventoryBase.objects.get(uuid=data['uuid'])
        except ObjectDoesNotExist:
            self.LOGGER.error('Asset not found')
            return Response({'error': 'Asset not found'}, status=404)
        except Exception as e:
            self.LOGGER.error(f'Error retrieving asset: {e}')
            return Response({'error': f'Error retrieving asset: {e}'},
                            status=500)

        try:
            # update asset
            asset_serializer = InventoryBaseSerializer(asset_query, data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
        except ValidationError as ve:
            self.LOGGER.error(f'Error updating asset: {ve}')
            return Response({'error': str(ve)}, status=400)
        except Exception as e:
            self.LOGGER.error(f'Error updating asset: {e}')
            return Response({'error': f'Error updating asset: {e}'},
                            status=500)

        if 'template_inventory' in data:
            sectionsArray = data.pop('template_inventory')

            for name, fields in sectionsArray.items():
                try:
                    # retrieve section ID
                    section_query = Section.objects.get(
                        name=name,
                        template=asset_instance.template_id
                        )
                except ObjectDoesNotExist:
                    errors.append(f'Section {name} not found')
                    continue
                except Exception as e:
                    errors.append(f'Error retrieving section {name}: {e}')
                    continue

                try:
                    # delete existing sections
                    InventorySection.objects.filter(
                        base=asset_instance.id,
                        template_section=section_query.id
                        ).delete()
                except Exception as e:
                    errors.append(f'Error deleting existing sections '
                                  f'for {name}: {e}')

                for field_object in fields:
                    try:
                        # create InventorySection
                        section_serializer = InventorySectionSerializer(
                            data={'base': asset_instance.id,
                                  'template_section': section_query.id}
                                )
                        if section_serializer.is_valid(
                                raise_exception=True
                                ):
                            section_instance = section_serializer.save()
                    except ValidationError as ve:
                        errors.append(f'Error creating section {name} '
                                      f': {str(ve)}')
                        continue
                    except Exception as e:
                        errors.append(
                            f'Error creating section {name}: {e}'
                            )
                        continue

                    # loop through each field object in fields array
                    for field_name, field_value in field_object.items():
                        try:
                            # retrieve field ID
                            field_query = Field.objects.get(
                                    name=field_name,
                                    section=section_query.id
                                    )
                        except ObjectDoesNotExist:
                            errors.append(f'Field {field_name} not found '
                                          f'in section {name}')
                            continue
                        except Exception as e:
                            errors.append(
                                f'Error retrieving field {field_name} '
                                f'in section {name}: {e}'
                                )
                            continue

                        try:
                            field_serializer = InventoryFieldSerializer(
                                data={'inventory_section':
                                      section_instance.id,
                                      'template_field': field_query.id,
                                      'value': field_value}
                                    )
                            if field_serializer.is_valid(
                                    raise_exception=True
                                    ):
                                field_serializer.save()
                        except ValidationError as ve:
                            errors.append(f'Error creating field {name} '
                                          f'- {field_name} : {str(ve)}')
                            continue
                        except Exception as e:
                            errors.append(
                                f'Error creating field {name} '
                                f'- {field_name}: {e}'
                                )
                            continue

        if errors:
            self.LOGGER.error('Partial update succeeded but errors were '
                              'encountered while updating device %s - %s: %s',
                              data['uuid'], data['name'], errors)
            return Response({'errors': errors}, status=200)
        else:
            self.LOGGER.info(
                            'Inventory updated successfully for device %s - %s'
                            ' sending response back to client', data['uuid'],
                            data['name'])

        return Response(
            {'message': 'Asset and inventory updated successfully'
             }, status=200)
