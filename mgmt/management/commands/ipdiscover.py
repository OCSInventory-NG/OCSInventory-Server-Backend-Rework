from django.core.management.base import BaseCommand
from ipdiscover.network.models import Network
from ipdiscover.netdevice.models import Netdevice
from django.forms.models import model_to_dict

import nmap
import re

from ipdiscover.network.serializers import NetworkSerializer

class Command(BaseCommand):
    """Name of the file equals command, e.g. 'demo'

    Args:
        BaseCommand ([type]): base class for management commands
    """

    help = 'any arg passed to this cmd will be printed back'

    def add_arguments(self, parser):
        """Add custom argument

        Args:
            parser ([type]): [description]
        """
        parser.add_argument('--network', action='append', type=str, help='targeted network for nmap scan (e.g. 172.18.26.0/24)')
        parser.add_argument('--list', action='store_true', help='')

    def handle(self, *args, **options):
        """Must be implemented, defines the logic behind the command"""
        
        def ipd_scan_subnet(subnet):
            """Scan subnets with nmap

            Args:
                subnet ([str]): e.g. 172.18.26.0/24
            """

            
            nm = nmap.PortScanner()
            results = []
            # multiple network might have been passed in args
            for net in subnet:
                result = nm.scan(hosts=net, arguments='-sP')
                print("IpDiscover scan found "+ result['nmap']['scanstats']['uphosts'] + " hosts for subnet " + net + " in " + result['nmap']['scanstats']['elapsed'] + "s.")
                net = re.sub('/24', '', net)
                data = {"name": "testnetwork", "description": "ipd from server watch this", "netid": net, "mask": "255.255.255.0", 
                        "netdevices": []}

                for device in result['scan'] :
                    netname = result['scan'][device]['hostnames'][0]['name']
                    data['netdevices'].append({"ip" : device, "netname" : netname, "mac" : "55:55:55:55:55"}) 

                results.append(data)
            
            network = NetworkSerializer()
            for res in results:
                NetworkSerializer.create(network, res)


        def ipd_device_lookup():
            pass

        def ipd_list():
            """Get all networks discovered

            Returns:
                [dict]: 
            """
            networks = Network.objects.all()
            networks_list = []
            for obj in networks:
                networks_list += [model_to_dict(obj)]

            return networks_list

        def xml_dump():
            pass


        if options['network']:
            network = options['network']
            ipd_scan_subnet(network)
            output = 'IpDiscover scan runned successfully'

        elif options['list']:
            output = ipd_list()


        
        self.stdout.write(str(output))
