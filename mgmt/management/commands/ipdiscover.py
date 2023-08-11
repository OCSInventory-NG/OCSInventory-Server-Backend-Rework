from django.core.management.base import BaseCommand, CommandError
from django.forms.models import model_to_dict
from ipdiscover.netdevice.models import Netdevice
from ipdiscover.network.models import Network

import logging

from ipaddress import AddressValueError, IPv4Network
import csv
import nmap
import subprocess
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
        # ipd scan args = --scantype --network --name --description --nettag
        parser.add_argument('--scantype', action='append', type=str,
                            help='Ipdiscover scan type (either nmap or fping')
        parser.add_argument('--network', action='append', type=str,
                            help='Cidr notation')
        parser.add_argument('--name', action='append', type=str,
                            help='Name of the subnet')
        parser.add_argument('--description', action='append', type=str,
                            help='Description of subnet')
        parser.add_argument('--nettag', action='append', type=str,
                            help='Unique id, by default will be netid of the subnet')
        # ipd list
        parser.add_argument('--list', action='store_true',
                            help='List already scanned subnets')
        # import ipd scan arguments from csv file
        parser.add_argument('--file', type=str,
                            help='Scan multiple networks by importing a csv file')
        # logging level
        parser.add_argument('--debug', action='store_true',
                            help='Set logging level to debug')

    def handle(self, *args, **options):
        """Must be implemented, defines the logic behind the command"""

        def from_file(file):
            """Import targeted subnets from CSV file

            Args:
                file ([str]): path to CSV file
            """
            static_fields = ['network', 'nettag', 'name', 'description']
            imported_fields = []
            with open(file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    # get fields from file
                    if 'network' in row:
                        for field in row:
                            imported_fields += [field]
                            options[field] = dict()
                    else:
                        network = row[0]
                        for field in imported_fields:
                            options[field][network] = row[imported_fields.index(field)]

            if not set(static_fields) == set(imported_fields):
                logger.info("Please check that all required fields are present in the "
                            "csv file (network,nettag,name,description)")
                exit()

        def ipd_list():
            """Get list of discovered networks

            Returns:
                [dict]: already scanned network infos
            """
            networks = Network.objects.all()
            networks_list = []
            for obj in networks:
                networks_list += [model_to_dict(obj)]

            return networks_list

        def ipd_scan_subnet(scantype, subnet, nettag, name, desc):
            """Scan subnets (either nmap or fping)

            Args:
                subnet ([str]): e.g. 172.18.26.0/24
            """

            def fping_scan(net):
                """Scan devices present on specific subnet and return their ip addresses
                 if alive

                Args:
                    net ([str]): e.g. 172.18.26.0/24
                """
                ping_cmd = ['fping', '-g',  '--quiet',  '-a', str(net)]
                process = subprocess.Popen(ping_cmd, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, encoding='utf-8')
                output = process.stdout.read()
                results = output.split()
                logger.info("IpDiscover scan found " + str(len(results))
                            + " hosts for subnet " + net)
                return results

            def nmap_scan(net):
                """Scan devices present on specific submet and return their ip addresses
                 and mac addresses if available

                Args:
                    net ([str]): e.g. 172.18.26.0/24
                """
                nm = nmap.PortScanner()
                results = nm.scan(hosts=net, arguments='-sP')

                try:
                    nb_hosts = results['nmap']['scanstats']['uphosts']
                    logger.info("IpDiscover scan found "
                                + nb_hosts
                                + " hosts for subnet " + net)
                    results = results['scan']
                except TypeError:
                    logger.debug("Nmap output is empty")
                return results

            def insert_netdevices(subnet, network_id):
                for netdevice in subnet["netdevices"]:
                    if netdevice['ip'] is not None:
                        # check if netdevice exists in db
                        existing_devices = Netdevice.objects.all()
                        if existing_devices.filter(ip=netdevice["ip"],
                                                   network=network_id).exists():
                            # update netdevice
                            netdevice_obj = existing_devices.get(ip=netdevice["ip"],
                                                                 network=network_id)
                            netdevice_obj.ip = netdevice['ip']
                            netdevice_obj.mac = netdevice['mac']
                            netdevice_obj.save()

                        else:
                            # create new netdevice
                            existing_devices.create(mac=netdevice['mac'],
                                                    ip=netdevice['ip'],
                                                    network=network_id)

            def insert_subnet(subnets):
                """Insert subnets and related netdevices into database

                Args:
                    subnets ([dict]): dict of subnets w/ netdevices discovered by either
                     nmap or fping scan
                """
                for subnet in subnets:
                    # check if subnet exists in db
                    existing_sub = Network.objects.all()
                    if existing_sub.filter(nettag=subnet["nettag"]).exists():
                        logger.debug("Subnet " + subnet["nettag"] +
                                     " already exists in database, " +
                                     "updating ..")
                        # update subnet
                        try:
                            subnet_obj = existing_sub.get(nettag=subnet["nettag"])
                            # name and description shouldn't be updated if not provided
                            if subnet["name"] != subnet["netid"]:
                                subnet_obj.name = subnet["name"]
                            if subnet["description"] != "":
                                subnet_obj.description = subnet["description"]

                            subnet_obj.nettag = subnet["nettag"]
                            subnet_obj.mask = subnet["mask"]
                            subnet_obj.save()
                            logger.debug("Subnet " + subnet["nettag"]
                                         + " updated in database")
                            # also update netdevices
                            insert_netdevices(subnet, subnet_obj)
                        except Exception as e:
                            logger.error("Error while updating subnet "
                                         + subnet["nettag"] + e)
                    else:
                        # create new subnet
                        try:
                            subnet_obj = existing_sub.create(
                                                            netid=subnet["netid"],
                                                            name=subnet["name"],
                                                            description=subnet["description"],
                                                            mask=subnet["mask"],
                                                            nettag=subnet["nettag"])
                            logger.debug("Subnet " + subnet["nettag"]
                                         + " created in database")
                            # create new netdevices
                            insert_netdevices(subnet, subnet_obj)
                        except Exception as e:
                            logger.error("Error while creating subnet "
                                         + subnet["nettag"] + e)

            if os.geteuid() != 0:
                logger.info("Running this command as unprivileged user will not provide"
                            " optimal results. Consider running as root instead.")

            # assign default value to name, desc and nettag if scan is missing any
            key = list(subnet.keys())[0]
            if len(subnet) == 1:
                if name[subnet[key]] is None:
                    name[subnet[key]] = re.sub('/24', '', subnet[key])
                if desc[subnet[key]] is None:
                    desc[subnet[key]] = ""
                if nettag[subnet[key]] is None:
                    # nettag is modified later in the process but still needs a default
                    nettag[subnet[key]] = ""

            results = []
            for net, tag, name, desc in zip(subnet.items(), nettag.items(),
                                            name.items(), desc.items()):
                # access values of key in dict
                net = net[1]
                ip = re.sub('/24', '', net)
                tag = tag[1] if tag[1] is not None else ""
                if not name[1]:
                    name = ip
                else:
                    name = name[1]
                desc = desc[1] if desc[1] is not None else ""

                try:
                    netmask = str(IPv4Network(net).netmask)
                except AddressValueError:
                    logger.info("Invalid subnet provided (" + ip +
                                "), no update will be " +
                                "performed, exiting ..")
                    exit()

                # nettag is reconciliation field = needs at least a default value
                if tag == "":
                    subnettag = ip
                else:
                    subnettag = ip + ":" + tag
                data = {"nettag": subnettag, "name": name, "description": desc,
                        "netid": ip, "mask": netmask, "netdevices": []}

                if scantype is not None and scantype[0] == 'fping':
                    logger.debug("Scanning subnet " + net + " with fping ..")
                    result = fping_scan(net)
                    for device in result:
                        netname = ''
                        # fping scan will not return mac, use ip instead
                        mac = device
                        data['netdevices'].append({"ip": device, "netname": netname,
                                                   "mac": mac})

                    results.append(data)

                elif scantype is not None and scantype[0] == 'nmap':
                    logger.debug("Scanning subnet " + net + " with nmap ..")
                    result = nmap_scan(net)
                    for device in result:
                        netname = result[device]['hostnames'][0]['name']
                        # if scan didn't return mac addresses > use ip instead
                        if 'mac' not in result[device]['addresses']:
                            mac = device
                        else:
                            mac = result[device]['addresses']['mac']
                        data['netdevices'].append({"ip": device, "netname": netname,
                                                   "mac": mac})
                    results.append(data)

                else:
                    logger.info("Please make sure to provide a supported --scantype"
                                " (nmap or fping), exiting process ..")
                    exit()

            insert_subnet(results)

        # IPD MAIN PROCESS

        # logger initialization
        logger = logging.getLogger('ipdiscover')
        logger.info("Starting ipdiscover scan ! ")
        if options['debug']:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        if options['network']:
            try:
                subnet = options['network'][0]
                # building dicts for this subnet
                network, nettag, name, description = {}, {}, {}, {}
                # assign key to dict
                network[subnet] = subnet
                nettag[subnet] = options['nettag'][0] if options['nettag'] else None
                name[subnet] = options['name'][0] if options['name'] else None
                if options['description']:
                    description[subnet] = options['description'][0]
                else:
                    description[subnet] = options['description'] = None

                ipd_scan_subnet(options['scantype'], network,
                                nettag, name,
                                description)
                logger.info('IpDiscover scan ran successfully.')
            except CommandError as e:
                logger.info("IpDiscover failed : " + str(e.__cause__))

        elif options['file']:
            logger.info("Please be aware that importing a file " +
                        " will overwrite any existing value.")
            try:
                from_file(options['file'])
                ipd_scan_subnet(options['scantype'], options['network'],
                                options['nettag'], options['name'],
                                options['description'])
                logger.info("IpDiscover scan ran successfully.")
            except CommandError as e:
                logger.info("IpDiscover failed : " + str(e.__cause__))

        elif options['list']:
            output = "Already discovered subnets : \n"
            for subnet in ipd_list():
                nettag = subnet['nettag']
                netid = subnet['netid']
                mask = subnet['mask']
                name = subnet['name']
                description = subnet['description'] if subnet['description'] else 'None'
                location = subnet['location'] if subnet['location'] else 'None'
                # concatenate all data to display
                output += ("Subnet " + nettag + " (" + netid + "/" + mask + ")"
                           + " - name : " + name + " - description : "
                           + description + " - location : " + location + "\n")
            logger.info(output)
