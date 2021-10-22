from django.core.management.base import BaseCommand
from django.forms.models import model_to_dict

from ipdiscover.network.serializers import NetworkSerializer
from ipdiscover.network.models import Network


from ipaddress import IPv4Network
import csv
import nmap
import re


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
        # ipd scan args = --network --name --description --nettag
        parser.add_argument('--network', action='append', type=str, help='Cidr notation')
        parser.add_argument('--name', action='append', type=str, help='Name of the subnet')
        parser.add_argument('--description', action='append', type=str, help='Description of subnet')
        parser.add_argument('--nettag', action='append', type=str, help='Unique id, by default will be netid of the subnet')
        # ipd list
        parser.add_argument('--list', action='store_true', help='')
        # import ipd scan arguments from csv file
        parser.add_argument('--file', type=str, help='Scan multiple networks by importing a csv file')
        

    def handle(self, *args, **options):
        """Must be implemented, defines the logic behind the command"""
        
        def ipd_scan_subnet(subnet, nettag, name, desc):
            """Scan subnets with nmap

            Args:
                subnet ([str]): e.g. 172.18.26.0/24
            """
            nm = nmap.PortScanner()
            results = []
            
            # multiple networks might have been passed in args
            for net, tag, name, desc in zip(subnet, nettag, name, desc):
                netmask = str(IPv4Network(net).netmask)
                result = nm.scan(hosts=net, arguments='-sP')
                print("IpDiscover scan found "+ result['nmap']['scanstats']['uphosts'] + " hosts for subnet " + net + " in " + result['nmap']['scanstats']['elapsed'] + "s.")
                net = re.sub('/24', '', net)
                # nettag is required, set a default value if not provided by the user
                if options['nettag'] != 'default':
                    subnettag = net + ":" + tag
                else:
                    subnettag = net
                data = {"nettag": subnettag, "name": name, "description": desc, "netid": net, "mask": netmask, 
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

        def from_file(file):
            """Import targeted subnets from CSV file

            Args:
                file ([str]): path to CSV file
            """
            fields = []
            with open(file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    #get fields name
                    if 'network' in row:
                        for field in row:
                            fields += [field]
                            options[field] = []
                    else :
                        for elem, field in zip(row, fields):
                                options[field] += [elem]
            print('Data imported from CSV')
            

        def ipd_list():
            """Get all networks discovered

            TODO : return linked netdevices ?

            Returns:
                [dict]: 
            """
            networks = Network.objects.all()
            networks_list = []
            for obj in networks:
                networks_list += [model_to_dict(obj)]

            return networks_list


        # assign default value to name, desc and nettag if missing any
        if options['name'] == None:
            options['name'] = re.sub('/24', '', str(options['network']))
        if options['description'] == None:
            options['description'] = 'default description'
        if options['nettag'] == None:
            # nettag is modified later in the process but still needs a default
            options['nettag'] = 'default'

        if options['network']:
            try:
                ipd_scan_subnet(options['network'], options['nettag'], options['name'], options['description'])
                output = 'IpDiscover scan ran successfully'
            except :
                output = 'IpDiscover scan failed'

        elif options['file']:
            try:
                from_file(options['file'])
                ipd_scan_subnet(options['network'], options['nettag'], options['name'], options['description'])
                output = 'IpDiscover scan ran successfully'
            except Exception as e:
                output = "IpDiscover failed : " + str(e.__cause__)

        elif options['list']:
            output = ipd_list()


        
        self.stdout.write(str(output))
