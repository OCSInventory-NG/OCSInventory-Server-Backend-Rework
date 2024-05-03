from rest_framework.parsers import BaseParser



import logging


from django.core.exceptions import ObjectDoesNotExist

from rest_framework.response import Response
from inventory.template.models import Template

import xmltodict

class LegacyXMLParser(BaseParser):
    media_type = 'application/xml'
    LOGGER = logging.getLogger(__name__)

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as XML and returns the resulting data.
        """
        data = xmltodict.parse(stream.read())
        
        template_data = {}
        template_data['name'] = data['REQUEST']['CONTENT']['HARDWARE']['NAME']
        template_data['description'] = data['REQUEST']['CONTENT']['HARDWARE']['DESCRIPTION']
        template_data['serial'] = data['REQUEST']['CONTENT']['BIOS']['SSN']
        template_data['osname'] = data['REQUEST']['CONTENT']['HARDWARE']['OSNAME']
        template_data['osversion'] = data['REQUEST']['CONTENT']['HARDWARE']['OSVERSION']
        template_data['uuid'] = data['REQUEST']['CONTENT']['HARDWARE']['UUID']

        # If the ipaddr contain multiple ip addresses, split them and add the first one to the dictionary
        ipaddr = data['REQUEST']['CONTENT']['HARDWARE']['IPADDR'].split('/')[0]
        template_data['srcip'] = ipaddr

        # Get mac address if the network is up
        for network in data['REQUEST']['CONTENT']['NETWORKS']:
            if network['STATUS'] == 'Up':
                template_data['srcmac'] = network['MACADDR']
                break
           
            
        template_data['domain'] = data['REQUEST']['CONTENT']['HARDWARE']['DNS']

        try:
            # retrieve template id where template's name is legacy
            template_data['template'] = Template.objects.get(name="Legacy").id
        except ObjectDoesNotExist:
            self.LOGGER.error("Template legacy not found")
            return Response({"error": "Template legacy  not found"}, status=404)
        except Exception as e:
            self.LOGGER.error(f"Error retrieving template legacy: {e}")
            return Response({"error": f"Error retrieving template legacy: {e}"}, status=500)
        
        # Transforming the section to a list if it is a dictionary
        template_inventory = {}
        for key, value in data['REQUEST']["CONTENT"].items():
            if isinstance(value, dict):
                template_inventory[key] = [value]
            else:
                template_inventory[key] = value
        template_data["template_inventory"] = template_inventory

        return template_data
            
