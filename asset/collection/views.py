from asset.inventory.serializers import InventorySectionSerializer, InventoryFieldSerializer
from ocsinventory_backend.ocs_framework import viewsets
from asset.base.serializers import BaseSerializer
from permission.permissions import DefaultModelPermissions
from asset.inventory.models import InventorySection, InventoryField
from inventory.section.models import Section
from inventory.field.models import Field
from inventory.section.serializers import SectionSerializer
from rest_framework.views import APIView

from rest_framework.response import Response

class CollectionView(APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):
        pass
        data = request.data

        # create Base asset using BaseSerializer
        asset_serializer = BaseSerializer(data=data)
        if asset_serializer.is_valid():
            asset_instance = asset_serializer.save()
            templateId = asset_instance.template_id if asset_instance.template else None
        else:
            return Response(asset_serializer.errors, status=400)

        # handle template inventory if present
        if 'template_inventory' in data:
            sectionsJson = data.pop('template_inventory')

            # loop through sections and create Inventory items
            for name, section_data in sectionsJson.items():
                # retrieve section ID
                section_query = Section.objects.filter(name=name, template=templateId)
                if not section_query.exists():
                    continue  # skip if no matching section found
                sectionId = section_query.first().id

                # create InventorySection
                inventory_section_serializer = InventorySectionSerializer(data={'base': asset_instance.id, 'template_section': sectionId})
                if inventory_section_serializer.is_valid():
                    inventory_section_instance = inventory_section_serializer.save()
                else:
                    return Response(inventory_section_serializer.errors, status=400)
                
                # loop through fields and create InventoryField items
                for field_name, field_value in section_data.items():
                    # retrieve field ID
                    field_query = Field.objects.filter(name=field_name, section=sectionId)
                    if not field_query.exists():
                        continue
                    fieldId = field_query.first().id

                    # create InventoryField
                    inventory_field_serializer = InventoryFieldSerializer(data={'inventory_section': inventory_section_instance.id, 'template_field': fieldId, 'value': field_value})
                    if inventory_field_serializer.is_valid():
                        inventory_field_instance = inventory_field_serializer.save()
                    else:
                        return Response(inventory_field_serializer.errors, status=400)
                    


        # successful creation response
        return Response({'message': 'Asset and inventory created successfully'}, status=201)
            

            

