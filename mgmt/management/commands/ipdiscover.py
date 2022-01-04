from django.core.management.base import BaseCommand, CommandError
from django.forms.models import model_to_dict

from ipdiscover.network.serializers import NetworkSerializer
from ipdiscover.network.models import Network


from ipaddress import IPv4Network
import csv
import nmap
import subprocess
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
        # ipd scan args = --scantype --network --name --description --nettag
        parser.add_argument('--scantype', action='append', type=str, help='Ipdiscover scan type (either nmap or fping')
        parser.add_argument('--network', action='append', type=str, help='Cidr notation')
        parser.add_argument('--name', action='append', type=str, help='Name of the subnet')
        parser.add_argument('--description', action='append', type=str, help='Description of subnet')
        parser.add_argument('--nettag', action='append', type=str, help='Unique id, by default will be netid of the subnet')
        # ipd list
        parser.add_argument('--list', action='store_true', help='List already scanned subnets')
        # import ipd scan arguments from csv file
        parser.add_argument('--file', type=str, help='Scan multiple networks by importing a csv file')
        

    def handle(self, *args, **options):
        """Must be implemented, defines the logic behind the command"""

        def ipd_scan_subnet(scantype, subnet, nettag, name, desc):
            """Scan subnets (either nmap or fping)

            Args:
                subnet ([str]): e.g. 172.18.26.0/24
            """

            def fping_scan(net):
                """Scan devices present on specific subnet and return their ip addresses if alive

                Args:
                    net ([str]): e.g. 172.18.26.0/24
                """
                ping_cmd = ['fping', '-g',  '--quiet',  '-a', str(net)] 
                process = subprocess.Popen(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
                output = process.stdout.read()
                result = output.split()
                print("IpDiscover scan found " + str(len(result)) + " hosts for subnet " + net)

                return result

            def nmap_scan(net):
                """Scan devices present on specific submet and return their ip addresses and mac addresses if available

                Args:
                    net ([str]): e.g. 172.18.26.0/24
                """
                nm = nmap.PortScanner()
                results = nm.scan(hosts=net, arguments='-sP')
                print("IpDiscover scan found "+ results['nmap']['scanstats']['uphosts'] + " hosts for subnet " + net)
                results = results['scan']

                return results

            def insert_subnet(subnets):
                """Insert subnets and related netdevices into database

                Args:
                    subnets ([dict]): dict of subnets w/ netdevices discovered by either nmap or fping scan
                """
                network = NetworkSerializer()
                for sub in subnets:
                    try:
                        NetworkSerializer.create(network, sub)
                    except Exception as e:
                        print('Failed to insert subnet ' + sub['netid'] + ' into database, see error : ' + str(e.__cause__))
                return 

            # assign default value to name, desc and nettag if unique scan is missing any
            if len(subnet) == 1:
                if name == None:
                    name = [re.sub('/24', '', subnet[0])]
                if desc == None:
                    desc = ['default description']
                if nettag == None:
                    # nettag is modified later in the process but still needs a default
                    nettag = ['default']

            results = []
            
            for net, tag, name, desc in zip(subnet, nettag, name, desc):          
                ip = re.sub('/24', '', net)
                netmask = str(IPv4Network(net).netmask)
                # nettag is required, set a default value if not provided by the user
                if tag != 'default':
                    subnettag = ip + ":" + tag
                else:
                    subnettag = ip
                data = {"nettag": subnettag, "name": name, "description": desc, "netid": ip, "mask": netmask, 
                        "netdevices": []}

                if scantype[0] == 'fping':
                    result = fping_scan(net)
                    for device in result:
                        netname = ''
                        # fping scan will not return mac, use ip instead
                        mac = device
                        data['netdevices'].append({"ip" : device, "netname" : netname, "mac" : mac})

                    results.append(data)
                    # print(results)

                elif scantype[0] == 'nmap':
                    result = nmap_scan(net)
                    for device in result:
                        netname = result[device]['hostnames'][0]['name']
                        # if scan didn't return mac addresses > use ip instead 
                        if not 'mac' in result[device]['addresses']:
                            mac = device
                        else:
                            mac = result[device]['addresses']['mac']
                            print('device is : ' + device)
                
                        data['netdevices'].append({"ip" : device, "netname" : netname, "mac" : mac})

                    results.append(data)
                    # print(results)

            insert_subnet(results)

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
                [dict]: already scanned network infos
            """
            networks = Network.objects.all()
            networks_list = []
            for obj in networks:
                networks_list += [model_to_dict(obj)]

            return networks_list


        if options['network']:
            try:
                ipd_scan_subnet(options['scantype'], options['network'], options['nettag'], options['name'], options['description'])
                output = 'IpDiscover scan ran successfully'
            except CommandError as e:
                output = "IpDiscover failed : " + str(e.__cause__)

        elif options['file']:
            try:
                from_file(options['file'])
                ipd_scan_subnet(options['scantype'], options['network'], options['nettag'], options['name'], options['description'])
                output = 'IpDiscover scan ran successfully'
            except CommandError as e:
                output = "IpDiscover failed : " + str(e.__cause__)

        elif options['list']:
            output = ipd_list()


        
        self.stdout.write(str(output))
