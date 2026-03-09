import ipaddress
import logging

from accountinfo.views import AccountinfoDataViewSet
from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from config.models import Config
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.software.services import SoftwareDictionaryService
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

    def check_blacklist(self, data):
        """
        Load the blacklist configuration and check if any of the device fields
        are blacklisted

        The configuration structure is as follows:
          - 1st dict contains the enabled switch
          - 2nd dict contains a comma separated string with the blocked values

        Ipaddresses should be in CIDR notation

        Returns (blacklisted, message)
        """
        try:
            config = Config.objects.get(name="blacklist")
            blacklist_config = config.value
        except Config.DoesNotExist:
            self.LOGGER.warning(
                "Blacklist configuration not found in database",
                extra={"classname": __name__},
            )
            return False, None

        for group in blacklist_config:
            # validating config format (grp = [switch, list_entry])
            if not isinstance(group, list) or len(group) < 2:
                continue

            switch = group[0]
            list_entry = group[1]

            # macaddress blacklist
            if switch.get("name") == "macaddresses" and switch.get("value"):
                blacklist_list = []
                for item in list_entry.get("value", "").split(","):
                    stripped_item = item.strip()
                    if stripped_item:
                        blacklist_list.append(stripped_item.upper())
                device_mac = data.get("srcmac", "").strip().upper()
                if device_mac and device_mac in blacklist_list:
                    self.LOGGER.debug(
                        f"Blacklisted MAC address detected: {device_mac}",
                        extra={"classname": __name__},
                    )
                    return True, f"MAC address {device_mac} is blacklisted."

            # ipaddress blacklist
            elif switch.get("name") == "ipaddresses" and switch.get("value"):
                # we expect CIDR
                cidr_list = [
                    item.strip()
                    for item in list_entry.get("value", "").split(",")
                    if item.strip()
                ]
                device_ip = data.get("srcip", "").strip()
                if device_ip:
                    try:
                        ip_obj = ipaddress.ip_address(device_ip)
                    except ValueError:
                        self.LOGGER.warning(
                            f"Invalid IP address format: {device_ip}",
                            extra={"classname": __name__},
                        )
                        continue

                    for cidr in cidr_list:
                        try:
                            network = ipaddress.ip_network(cidr, strict=False)
                            if ip_obj in network:
                                self.LOGGER.debug(
                                    f"""
                                                  Blacklisted IP address detected:
                                                   {device_ip} (matches CIDR {cidr})""",
                                    extra={"classname": __name__},
                                )
                                return (
                                    True,
                                    f"""IP address {device_ip}
                                  is blacklisted (matches CIDR {cidr}).""",
                                )
                        except ValueError:
                            self.LOGGER.warning(
                                f"Invalid CIDR notation: {cidr}",
                                extra={"classname": __name__},
                            )
                            continue

            # serialnumber blacklist
            elif switch.get("name") == "serialnumbers" and switch.get("value"):
                blacklist_list = []
                for item in list_entry.get("value", "").split(","):
                    stripped_item = item.strip()
                    if stripped_item:
                        blacklist_list.append(stripped_item.upper())
                device_serial = data.get("serial", "").strip().upper()
                if device_serial and device_serial in blacklist_list:
                    self.LOGGER.debug(
                        f"""Blacklisted serial number detected:
                                       {device_serial}""",
                        extra={"classname": __name__},
                    )
                    return True, f"Serial number {device_serial} is blacklisted."

        return False, None

    def get_reconciliation_fields(self):
        """
        Get the fields used for reconciliation from the server configuration

        Possible values are:
         - "uuid"
         - "uuid, name"
         - "uuid, srcmac"
         Default is "uuid"
        """
        try:
            config = Config.objects.get(name="server")
            for item in config.value:
                if item.get("name") == "duplicate_reconciliation":
                    selection = item.get("value", "uuid")
                    if selection == "uuid, name":
                        fields = ["uuid", "name"]
                    elif selection == "uuid, srcmac":
                        fields = ["uuid", "srcmac"]
                    else:
                        # default or "uuid"
                        fields = ["uuid"]
                    self.LOGGER.debug(
                        f"Reconciliation fields configured as: {fields}",
                        extra={"classname": __name__},
                    )
                    return fields
            fields = ["uuid"]
            self.LOGGER.debug(
                f"Using default reconciliation fields: {fields}",
                extra={"classname": __name__},
            )
            return fields
        except Config.DoesNotExist:
            self.LOGGER.warning(
                """No server configuration found, will be using uuid only as
                  default reconciliation field""",
                extra={"classname": __name__},
            )
            fields = ["uuid"]
            self.LOGGER.debug(
                f"Using default reconciliation fields: {fields}",
                extra={"classname": __name__},
            )
            return fields

    def get_reconciliation_filter(self, data):
        """
        Build a filter for asset lookup from the reconciliation fields (config)
        """
        fields = self.get_reconciliation_fields()
        filter_dict = {}
        for field in fields:
            if field not in data:
                raise ValueError(
                    f"""Missing field '{field}'
                                  required for reconciliation."""
                )
            filter_dict[field] = data[field]
        return filter_dict

    def format_reconciliation_info(self, data):
        fields = self.get_reconciliation_fields()
        values = [f"{field}={data.get(field, 'unknown')}" for field in fields]
        return f"({' - '.join(values)})"

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
        reconciliation_info = self.format_reconciliation_info(data)
        device_id = f"{data.get('name', 'unknown')} {reconciliation_info}"

        # blacklist check
        blacklisted, message = self.check_blacklist(data)
        if blacklisted:
            self.LOGGER.debug(
                f"Device creation rejected - {device_id}: {message}",
                extra={"classname": __name__},
            )
            return Response(
                {
                    "message": f"""Device creation rejected due
                              to blacklist: {message}"""
                },
                status=403,
            )

        errors = []
        self.LOGGER.info(
            "Creating inventory for device %s",
            device_id,
            extra={"classname": __name__},
        )

        try:
            asset_serializer = InventoryBaseSerializer(data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
                templateId = (
                    asset_instance.template_id if asset_instance.template else None
                )
                # if accountinfo_generation is set to agent mode
                server_conf = Config.objects.filter(name="server").first()
                accountinfo_gen = None
                for item in server_conf.value:
                    if item["name"] == "admin_data_generation":
                        accountinfo_gen = item
                        break

                if accountinfo_gen["value"] == "agent":
                    # create accountinfo data for the new asset
                    AccountinfoDataViewSet.generate_accountinfo(
                        asset_instance, "inventory_base.inventorybase"
                    )
        except ValidationError as ve:
            self.LOGGER.error(
                "Error while creating inventory for device %s: %s",
                device_id,
                ve,
                extra={"classname": __name__},
            )
            return Response({"error": str(ve)}, status=400)
        except Exception as e:
            self.LOGGER.error(
                "Error while creating inventory for device %s: %s",
                device_id,
                e,
                extra={"classname": __name__},
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
                field.name: field for field in field_objs.filter(section=section)
            }
            for section in section_objs
        }

        # handle template inventory if present
        if "template_inventory" in data:
            sections_array = data.pop("template_inventory")

            sections_to_create = []
            fields_to_create = []

            for section_name, items in sections_array.items():
                section_obj = section_objs.filter(name=section_name).first()
                if not section_obj:
                    errors.append(f"Section {section_name} not found in template")
                    continue

                field_map = section_field_map.get(section_name, {})
                for item in items:
                    section_instance = InventorySection(
                        base=asset_instance, template_section=section_obj
                    )
                    sections_to_create.append(section_instance)

                    for field_name, field_value in item.items():
                        field_obj = field_map.get(field_name)
                        if not field_obj:
                            errors.append(
                                f"Field {field_name} not found "
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
            try:
                InventorySection.objects.bulk_create(sections_to_create)
                InventoryField.objects.bulk_create(fields_to_create)
            except Exception as exc:
                self.LOGGER.error(
                    "Error while bulk creating sections and fields: %s",
                    exc,
                    extra={"classname": __name__},
                )
                return Response(
                    {
                        "error": "Error while bulk creating sections and fields",
                        "details": str(exc),
                    },
                    status=500,
                )

        if errors:
            self.LOGGER.error(
                "Errors encountered while creating inventory for device %s: %s",
                device_id,
                errors,
                extra={"classname": __name__},
            )
            return Response(
                {
                    f"""Inventory created with errors for device {device_id}: {str(errors)}"""
                },
                status=201,
            )
        else:
            self.LOGGER.info(
                "Inventory created successfully for device %s",
                device_id,
                extra={"classname": __name__},
            )

        self._refresh_software_dictionary(asset_instance)

        # successful creation response
        return Response(
            {"message": "Inventory created successfully", "id": asset_instance.id},
            status=201,
        )

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
        reconciliation_info = self.format_reconciliation_info(data)
        device_id = f"{data.get('name', 'unknown')} {reconciliation_info}"

        # blacklist check
        blacklisted, message = self.check_blacklist(data)
        if blacklisted:
            self.LOGGER.debug(
                f"Device update rejected - {device_id}: {message}",
                extra={"classname": __name__},
            )
            return Response(
                {
                    "message": f"""Device update rejected due
                              to blacklist: {message}"""
                },
                status=403,
            )

        errors = []
        self.LOGGER.info(
            "Updating inventory for device %s",
            device_id,
            extra={"classname": __name__},
        )

        try:
            reconciliation_filter = self.get_reconciliation_filter(data)
        except ValueError as ve:
            self.LOGGER.error("Reconciliation error: %s", ve)
            return Response({"error": str(ve)}, status=400)

        asset_instance = InventoryBase.objects.filter(**reconciliation_filter).first()
        if not asset_instance:
            self.LOGGER.error(
                f"Error retrieving asset: {reconciliation_info}",
                extra={"classname": __name__},
            )
            return Response(
                {"error": f"Error retrieving asset: {reconciliation_info}"},
                status=500,
            )
        try:
            # update asset
            asset_serializer = InventoryBaseSerializer(asset_instance, data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
        except ValidationError as ve:
            self.LOGGER.error(
                "Error while updating inventory for device %s: %s",
                device_id,
                ve,
                extra={"classname": __name__},
            )
            return Response({"error": str(ve)}, status=400)
        except Exception as e:
            self.LOGGER.error(
                "Error while updating inventory for device %s: %s",
                device_id,
                e,
            )
            return Response({"error": f"Error while updating inventory: {e}"}, status=500)

        section_objs = Section.objects.filter(template=asset_instance.template_id)
        field_objs = Field.objects.filter(section__in=section_objs)
        section_field_map = {
            section.name: {
                field.name: field for field in field_objs.filter(section=section)
            }
            for section in section_objs
        }

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
                    section_instance = InventorySection(
                        base=asset_instance, template_section=section_obj
                    )
                    sections_to_create.append(section_instance)

                    for field_name, field_value in item.items():
                        field_obj = field_map.get(field_name)
                        if not field_obj:
                            errors.append(
                                f"No matching field found for {field_name}"
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
            try:
                InventorySection.objects.bulk_create(sections_to_create)
                InventoryField.objects.bulk_create(fields_to_create)
            except Exception as exc:
                self.LOGGER.error(
                    "Error while bulk creating sections and fields: %s",
                    exc,
                    extra={"classname": __name__},
                )
                return Response(
                    {
                        "error": "Error while bulk creating sections and fields",
                        "details": str(exc),
                    },
                    status=500,
                )
        if errors:
            self.LOGGER.error(
                "Update completed with errors for device %s: %s",
                device_id,
                errors,
                extra={"classname": __name__},
            )
            return Response(
                {
                    f"""Update succeeded but errors were encountered while
                      updating device {device_id}: {str(errors)}"""
                },
                status=200,
            )
        else:
            self.LOGGER.info(
                "Inventory updated successfully for device %s",
                device_id,
                extra={"classname": __name__},
            )

        self._refresh_software_dictionary(asset_instance)

        return Response(
            {"message": "Inventory updated successfully", "id": asset_instance.id},
            status=200,
        )

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
        reconciliation_info = self.format_reconciliation_info(data)
        device_id = f"{data.get('name', 'unknown')} {reconciliation_info}"

        # blacklist check
        blacklisted, message = self.check_blacklist(data)
        if blacklisted:
            self.LOGGER.debug(
                f"Device partial update rejected: {device_id}: {message}",
                extra={"classname": __name__},
            )
            return Response(
                {
                    "message": f"""Device partial update rejected
                              due to blacklist: {message}"""
                },
                status=403,
            )

        errors = []
        self.LOGGER.info(
            "Updating inventory for device %s",
            device_id,
            extra={"classname": __name__},
        )

        try:
            reconciliation_filter = self.get_reconciliation_filter(data)
        except ValueError as ve:
            self.LOGGER.error(
                "Reconciliation error: %s", ve, extra={"classname": __name__}
            )
            return Response({"error": str(ve)}, status=400)

        asset_instance = InventoryBase.objects.filter(**reconciliation_filter).first()
        if not asset_instance:
            self.LOGGER.error(
                f"Error retrieving asset: {reconciliation_info}",
                extra={"classname": __name__},
            )
            return Response(
                {"error": f"Error retrieving asset: {reconciliation_info}"},
                status=500,
            )

        try:
            # update asset
            asset_serializer = InventoryBaseSerializer(asset_instance, data=data)
            if asset_serializer.is_valid(raise_exception=True):
                asset_instance = asset_serializer.save()
        except ValidationError as ve:
            self.LOGGER.error(
                "Error while updating inventory for device %s: %s",
                device_id,
                ve,
                extra={"classname": __name__},
            )
            return Response({"error": str(ve)}, status=400)
        except Exception as e:
            self.LOGGER.error(
                "Error while updating inventory for device %s: %s",
                device_id,
                e,
                extra={"classname": __name__},
            )
            return Response({"error": f"Error updating asset: {e}"}, status=500)

        # pre-fetch Sections and Fields
        section_objs = Section.objects.filter(template=asset_instance.template_id)
        field_objs = Field.objects.filter(section__in=section_objs)
        section_field_map = {
            section.name: {
                field.name: field for field in field_objs.filter(section=section)
            }
            for section in section_objs
        }

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
                InventorySection.objects.filter(
                    base=asset_instance, template_section=section_query
                ).delete()

                field_map = section_field_map.get(section_name, {})
                for item in items:
                    section_instance = InventorySection(
                        base=asset_instance, template_section=section_query
                    )
                    new_sections.append(section_instance)

                    for field_name, field_value in item.items():
                        field_obj = field_map.get(field_name)
                        if not field_obj:
                            errors.append(
                                f"Field {field_name} not found"
                                f" in section {section_name}"
                            )
                            continue

                        new_field = InventoryField(
                            inventory_section=section_instance,
                            template_field=field_obj,
                            value=field_value,
                        )
                        new_fields.append(new_field)

            # bulk create sections and fields
            try:
                InventorySection.objects.bulk_create(new_sections)
                InventoryField.objects.bulk_create(new_fields)
            except Exception as exc:
                self.LOGGER.error(
                    "Error while bulk creating sections and fields: %s",
                    exc,
                    extra={"classname": __name__},
                )
                return Response(
                    {
                        "error": "Error while bulk creating sections and fields",
                        "details": str(exc),
                    },
                    status=500,
                )

        if errors:
            self.LOGGER.error(
                "Partial update completed with errors for device %s: %s",
                device_id,
                errors,
                extra={"classname": __name__},
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
                "Inventory updated successfully for device %s",
                device_id,
                extra={"classname": __name__},
            )

        self._refresh_software_dictionary(asset_instance)

        return Response(
            {
                "message": "Inventory updated successfully",
                "id": asset_instance.id,
            },
            status=200,
        )

    def _refresh_software_dictionary(self, asset_instance):
        if (
            not asset_instance
            or not SoftwareDictionaryService.should_refresh_on_inventory()
        ):
            return
        try:
            SoftwareDictionaryService.refresh_asset(asset_instance)
        except Exception as exc:
            self.LOGGER.exception(
                "Failed to refresh software dictionary for asset %s: %s",
                getattr(asset_instance, "id", "unknown"),
                exc,
                extra={"classname": __name__},
            )
