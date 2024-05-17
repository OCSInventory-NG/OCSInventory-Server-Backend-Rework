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

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as XML and returns the resulting data.
        """
        data_stream = stream.read()
        data = xmltodict.parse(zlib.decompress(data_stream))
        # Remove the decompression if you are debugging
        # data = xmltodict.parse(data_stream)

        template_data = {}
        if data["REQUEST"]["QUERY"] == "PROLOG":
            template_data["query"] = data["REQUEST"]["QUERY"]
        else:
            try:
                template_data["query"] = data["REQUEST"]["QUERY"]
            except KeyError:
                template_data["query"] = "-1"
            try:
                template_data["name"] = data["REQUEST"]["CONTENT"]["HARDWARE"]["NAME"]
            except KeyError:
                template_data["name"] = "-1"
            try:
                template_data["description"] = data["REQUEST"]["CONTENT"]["HARDWARE"][
                    "DESCRIPTION"
                ]
            except KeyError:
                template_data["description"] = "-1"
            try:
                template_data["serial"] = data["REQUEST"]["CONTENT"]["BIOS"]["SSN"]
            except KeyError:
                template_data["serial"] = "-1"
            try:
                template_data["osname"] = data["REQUEST"]["CONTENT"]["HARDWARE"][
                    "OSNAME"
                ]
            except KeyError:
                template_data["osname"] = "-1"
            try:
                template_data["osversion"] = data["REQUEST"]["CONTENT"]["HARDWARE"][
                    "OSVERSION"
                ]
            except KeyError:
                template_data["osversion"] = "-1"
            try:
                template_data["uuid"] = data["REQUEST"]["CONTENT"]["HARDWARE"]["UUID"]
            except KeyError:
                try:
                    for network in data["REQUEST"]["CONTENT"]["NETWORKS"]:
                        if network["STATUS"] == "Up":
                            template_data["uuid"] = (
                                data["REQUEST"]["CONTENT"]["HARDWARE"]["NAME"]
                                + "_"
                                + network["MACADDR"]
                            )
                            break
                except KeyError:
                    template_data["uuid"] = "-1"

            # If the ipaddr contain multiple ip addresses, split them and add the first one to the dictionary
            try:
                ipaddr = data["REQUEST"]["CONTENT"]["HARDWARE"]["IPADDR"].split("/")[0]
            except KeyError:
                ipaddr = "-1"
            template_data["srcip"] = ipaddr

            # Get mac address if the network is up
            try:
                for network in data["REQUEST"]["CONTENT"]["NETWORKS"]:
                    if network["STATUS"] == "Up":
                        template_data["srcmac"] = network["MACADDR"]
                        break
            except KeyError:
                template_data["srcmac"] = "-1"

            try:
                template_data["domain"] = data["REQUEST"]["CONTENT"]["HARDWARE"]["DNS"]
            except KeyError:
                template_data["domain"] = "-1"

            try:
                # retrieve template id where template's name is legacy
                template_data["template"] = Template.objects.get(name="Legacy").id
            except KeyError:
                template_data["template"] = "-1"
            except ObjectDoesNotExist:
                self.LOGGER.error("Template legacy not found")
                return Response({"error": "Template legacy  not found"}, status=404)
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

        self.LOGGER.info("test")

        return template_data
