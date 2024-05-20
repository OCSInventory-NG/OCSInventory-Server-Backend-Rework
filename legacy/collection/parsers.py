import logging
import xmltodict
import zlib

from django.core.exceptions import ObjectDoesNotExist
from inventory.template.models import Template
from rest_framework.parsers import BaseParser
from rest_framework.response import Response


class LegacyXMLParser(BaseParser):
    media_type = "application/*"
    LOGGER = logging.getLogger(__name__)

    def get_nested(self, data, keys, default="-1"):
        """Helper function to get a nested value from a dictionary."""
        for key in keys:
            try:
                data = data[key]
            except (KeyError, TypeError):
                return default
        return data or default

    def get_first_up_network_mac(self, networks):
        """Helper function to get the MAC address of the first network with status 'Up'."""
        for network in networks:
            if network.get("STATUS") == "Up":
                return network.get("MACADDR", "-1")
        return "-1"

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as XML and returns the resulting data.
        """
        decompressor = zlib.decompressobj()
        try:
            data_stream = decompressor.decompress(stream.read())
            data_stream += decompressor.flush()
        except zlib.error as e:
            print(f"Inflation failed: {e}")
        data = xmltodict.parse(data_stream.decode("utf-8"))
        # Remove the decompression if you are debugging
        # data = xmltodict.parse(stream.read())

        template_data = {}
        request_data = data.get("REQUEST", {}).get("CONTENT", {})

        # Set the query
        template_data["query"] = data.get("REQUEST", {}).get("QUERY", "-1")

        if template_data["query"] != "PROLOG":
            template_data["name"] = self.get_nested(request_data, ["HARDWARE", "NAME"])
            template_data["description"] = self.get_nested(
                request_data, ["HARDWARE", "DESCRIPTION"]
            )
            template_data["serial"] = self.get_nested(request_data, ["BIOS", "SSN"])
            template_data["osname"] = self.get_nested(
                request_data, ["HARDWARE", "OSNAME"]
            )
            template_data["osversion"] = self.get_nested(
                request_data, ["HARDWARE", "OSVERSION"]
            )
            template_data["uuid"] = self.get_nested(request_data, ["HARDWARE", "UUID"])
            if template_data["uuid"] == "-1":
                macaddr = self.get_first_up_network_mac(
                    request_data.get("NETWORKS", [])
                )
                if macaddr != "-1":
                    template_data["uuid"] = (
                        f"{self.get_nested(request_data, ['HARDWARE', 'NAME'])}_{macaddr}"
                    )

            template_data["srcip"] = self.get_nested(
                request_data, ["HARDWARE", "IPADDR"]
            ).split("/")[0]

            template_data["srcmac"] = self.get_first_up_network_mac(
                request_data.get("NETWORKS", [])
            )

            template_data["domain"] = self.get_nested(request_data, ["HARDWARE", "DNS"])

            try:
                template_data["template"] = Template.objects.get(name="Legacy").id
            except ObjectDoesNotExist:
                self.LOGGER.error("Template legacy not found")
                return Response({"error": "Template legacy not found"}, status=404)
            except Exception as e:
                self.LOGGER.error(f"Error retrieving template legacy: {e}")
                return Response(
                    {"error": f"Error retrieving template legacy: {e}"}, status=500
                )

            # Transforming the section to a list if it is a dictionary
            template_inventory = {}
            for key, value in data["REQUEST"]["CONTENT"].items():
                if isinstance(value, dict):
                    template_inventory[key] = [value]
                else:
                    template_inventory[key] = value
            template_data["template_inventory"] = template_inventory
        return template_data
