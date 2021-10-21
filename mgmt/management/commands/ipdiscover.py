from django.core.management.base import BaseCommand
from django.forms.models import model_to_dict

from ipdiscover.network.serializers import NetworkSerializer
from ipdiscover.network.models import Network


from ipaddress import IPv4Network
import nmap
import re
import os


class Command(BaseCommand):
    """Name of the file equals command, e.g. 'demo'

    Args:
        BaseCommand ([type]): base class for management commands
    """

    help = 'Launch IpDiscover scan with nmap'

    def add_arguments(self, parser):
        """Add custom argument

        Args:
            parser ([type]): [description]
        """
        # ipd scan args = --network (multi)
        parser.add_argument('--network', action='append', type=str, help='targeted network for nmap scan (e.g. 172.18.26.0/24)')
        # ipd list
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
                netmask = str(IPv4Network(net).netmask)
                result = nm.scan(hosts=net, arguments='-sP')
                print("IpDiscover scan found "+ result['nmap']['scanstats']['uphosts'] + " hosts for subnet " + net + " in " + result['nmap']['scanstats']['elapsed'] + "s.")
                net = re.sub('/24', '', net)
                data = {"name": net, "description": "ipd from server watch this", "netid": net, "mask": netmask, 
                        "netdevices": []}

                for device in result['scan'] :
                    netname = result['scan'][device]['hostnames'][0]['name']
                    # if nmap didn't return mac addresses > use ip instead 
                    if not 'mac' in result['scan'][device]['addresses']:
                        mac = device
                    else :
                        mac = result['scan'][device]['addresses']['mac']
                    
                    data['netdevices'].append({"ip" : device, "netname" : netname, "mac" : mac}) 

                results.append(data)
                # print(results)
            
            network = NetworkSerializer()
            for res in results:
                NetworkSerializer.create(network, res)


        def ipd_device_lookup():
            pass

        def ipd_list():
            """Get all networks discovered

            TODO : return linked netdevices

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
