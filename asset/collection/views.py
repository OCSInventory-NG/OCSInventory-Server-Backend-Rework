from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_section.serializers import InventorySectionSerializer
from asset.inventory_field.serializers import InventoryFieldSerializer
from inventory.section.models import Section
from inventory.field.models import Field
from rest_framework.views import APIView

from rest_framework.response import Response


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
