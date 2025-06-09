import csv
import logging
import os
import re
import subprocess
from ipaddress import AddressValueError, IPv4Network

import nmap
from django.core.management.base import BaseCommand, CommandError
from django.forms.models import model_to_dict
from ipdiscover.netdevice.models import Netdevice
from ipdiscover.network.models import Network


class Command(BaseCommand):
    """Name of the file equals command, e.g. 'demo'

    Args:
        BaseCommand ([type]): base class for management commands
    """

    help = "Launch IpDiscover scan with nmap"

    def add_arguments(self, parser):
        """Add custom argument

        Args:
            parser ([type]): [description]
        """
        # ipd scan args = --scantype --network --name --description --nettag
        parser.add_argument(
            "--scantype",
            action="append",
            type=str,
            help="Ipdiscover scan type (either nmap or fping",
        )
        parser.add_argument(
            "--network", action="append", type=str, help="Cidr notation"
        )
        parser.add_argument(
            "--name", action="append", type=str, help="Name of the subnet"
        )
        parser.add_argument(
            "--description", action="append", type=str, help="Description of subnet"
        )
        parser.add_argument(
            "--nettag",
            action="append",
            type=str,
            help="Unique id, by default will be netid of the subnet",
        )
        # ipd list
        parser.add_argument(
            "--list", action="store_true", help="List already scanned subnets"
        )
        # import ipd scan arguments from csv file
        parser.add_argument(
            "--file", type=str, help="Scan multiple networks by importing a csv file"
        )
        # make loglevel optional
        parser.add_argument(
            "--loglevel",
            type=str,
            choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
            help="Override logging level from server",
        )

    def handle(self, *args, **options):
        """Must be implemented, defines the logic behind the command"""

        # logger initialization
        logger = logging.getLogger("mgmt.management.commands")
        logger.debug(f"Command arguments: {options}")

        # only set log level if explicitly provided in args
        if options["loglevel"]:
            log_level = getattr(logging, options["loglevel"])
            logger.setLevel(log_level)
            logger.debug(f"Log level overridden to: {options['loglevel']}")
        else:
            logger.debug("Using log level from settings.py")

        logger.info("Starting ipdiscover scan!")

        def from_file(file):
            """Import targeted subnets from CSV file

            Args:
                file ([str]): path to CSV file
            """
            logger.debug(f"Reading CSV file: {file}")
            static_fields = ["network", "nettag", "name", "description"]
            imported_fields = []
            try:
                with open(file, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if "network" in row:
                            logger.debug(f"Found header row: {row}")
                            for field in row:
                                imported_fields += [field]
                                options[field] = dict()
                        else:
                            logger.debug(f"Processing network row: {row}")
                            network = row[0]
                            for field in imported_fields:
                                options[field][network] = row[
                                    imported_fields.index(field)
                                ]

                if not set(static_fields) == set(imported_fields):
                    missing_fields = set(static_fields) - set(imported_fields)
                    logger.error(f"Missing required fields in CSV: {missing_fields}")
                    exit()
            except FileNotFoundError:
                logger.error(f"CSV file not found: {file}")
                exit()
            except Exception as e:
                logger.error(f"Error reading CSV file: {str(e)}")
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
                logger.debug(f"Starting fping scan for network: {net}")
                ping_cmd = ["fping", "-g", "--quiet", "-a", str(net)]
                process = subprocess.Popen(
                    ping_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                )
                output = process.stdout.read()
                results = output.split()

                logger.debug(f"Fping scan completed. Raw output: {output}")
                logger.info(
                    f"IpDiscover scan found {len(results)}" f" hosts for subnet {net}"
                )
                return results

            def nmap_scan(net):
                """Scan devices present on specific submet and return their ip addresses
                 and mac addresses if available

                Args:
                    net ([str]): e.g. 172.18.26.0/24
                """
                logger.debug(f"Starting nmap scan for network: {net}")
                nm = nmap.PortScanner()

                try:
                    results = nm.scan(hosts=net, arguments="-sP")

                    try:
                        nb_hosts = results["nmap"]["scanstats"]["uphosts"]
                        logger.debug(f"Nmap scan results: {results}")
                        logger.info(
                            f"IpDiscover scan found {nb_hosts}"
                            f" hosts for subnet {net}"
                        )
                        results = results["scan"]
                    except TypeError:
                        logger.warning("Nmap output is empty")
                        results = {}
                except Exception as e:
                    logger.error(f"Nmap scan failed: {str(e)}")
                    results = {}

                return results

            def insert_netdevices(subnet, network_id):
                logger.debug(
                    f"Inserting/updating netdevices" f" for subnet: {subnet['nettag']}"
                )
                for netdevice in subnet["netdevices"]:
                    if netdevice["ip"] is not None:
                        logger.debug(
                            f"Processing netdevice: IP={netdevice['ip']},"
                            f" MAC={netdevice['mac']}"
                        )
                        # check if netdevice exists in db
                        existing_devices = Netdevice.objects.all()
                        if existing_devices.filter(
                            ip=netdevice["ip"], network=network_id
                        ).exists():
                            # update netdevice
                            netdevice_obj = existing_devices.get(
                                ip=netdevice["ip"], network=network_id
                            )
                            netdevice_obj.ip = netdevice["ip"]
                            netdevice_obj.mac = netdevice["mac"]
                            netdevice_obj.save()

                        else:
                            # create new netdevice
                            existing_devices.create(
                                mac=netdevice["mac"],
                                ip=netdevice["ip"],
                                network=network_id,
                            )

            def insert_subnet(subnets):
                """Insert subnets and related netdevices into database

                Args:
                    subnets ([dict]): dict of subnets w/ netdevices discovered by either
                     nmap or fping scan
                """
                logger.debug(
                    f"Processing {len(subnets)} subnets" f" for database insertion"
                )
                for subnet in subnets:
                    logger.debug(f"Processing subnet: {subnet['nettag']}")
                    # check if subnet exists in db
                    existing_sub = Network.objects.all()
                    if existing_sub.filter(nettag=subnet["nettag"]).exists():
                        logger.debug(
                            f"Subnet {subnet['nettag']} already exists"
                            f" in database, updating.."
                        )
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
                            logger.debug(
                                f"Subnet {subnet['nettag']}" f" updated in database"
                            )
                            # also update netdevices
                            insert_netdevices(subnet, subnet_obj)
                        except Exception as e:
                            logger.error(
                                f"Error while updating subnet"
                                f" {subnet['nettag']}: {str(e)}"
                            )
                    else:
                        # create new subnet
                        try:
                            subnet_obj = existing_sub.create(
                                netid=subnet["netid"],
                                name=subnet["name"],
                                description=subnet["description"],
                                mask=subnet["mask"],
                                nettag=subnet["nettag"],
                            )
                            logger.debug(
                                f"Subnet {subnet['nettag']}" f" created in database"
                            )
                            # create new netdevices
                            insert_netdevices(subnet, subnet_obj)
                        except Exception as e:
                            logger.error(
                                f"Error while creating subnet"
                                f" {subnet['nettag']}: {str(e)}"
                            )

            if os.geteuid() != 0:
                logger.info(
                    "Running this command as unprivileged user will not provide"
                    " optimal results. Consider running as root instead."
                )

            # assign default value to name, desc and nettag if scan is missing any
            key = list(subnet.keys())[0]
            if len(subnet) == 1:
                if name[subnet[key]] is None:
                    name[subnet[key]] = re.sub("/24", "", subnet[key])
                if desc[subnet[key]] is None:
                    desc[subnet[key]] = ""
                if nettag[subnet[key]] is None:
                    # nettag is modified later in the process but still needs a default
                    nettag[subnet[key]] = ""

            results = []
            for net, tag, name, desc in zip(
                subnet.items(), nettag.items(), name.items(), desc.items()
            ):
                # access values of key in dict
                net = net[1]
                ip = re.sub("/24", "", net)
                tag = tag[1] if tag[1] is not None else ""
                if not name[1]:
                    name = ip
                else:
                    name = name[1]
                desc = desc[1] if desc[1] is not None else ""

                try:
                    netmask = str(IPv4Network(net).netmask)
                except AddressValueError:
                    logger.info(
                        "Invalid subnet provided ("
                        + ip
                        + "), no update will be "
                        + "performed, exiting .."
                    )
                    exit()

                # nettag is reconciliation field = needs at least a default value
                if tag == "":
                    subnettag = ip
                else:
                    subnettag = ip + ":" + tag
                data = {
                    "nettag": subnettag,
                    "name": name,
                    "description": desc,
                    "netid": ip,
                    "mask": netmask,
                    "netdevices": [],
                }

                if scantype is not None and scantype[0] == "fping":
                    logger.debug("Scanning subnet " + net + " with fping ..")
                    result = fping_scan(net)
                    for device in result:
                        netname = ""
                        # fping scan will not return mac, use ip instead
                        mac = device
                        data["netdevices"].append(
                            {"ip": device, "netname": netname, "mac": mac}
                        )

                    results.append(data)

                elif scantype is not None and scantype[0] == "nmap":
                    logger.debug("Scanning subnet " + net + " with nmap ..")
                    result = nmap_scan(net)
                    for device in result:
                        netname = result[device]["hostnames"][0]["name"]
                        # if scan didn't return mac addresses > use ip instead
                        if "mac" not in result[device]["addresses"]:
                            mac = device
                        else:
                            mac = result[device]["addresses"]["mac"]
                        data["netdevices"].append(
                            {"ip": device, "netname": netname, "mac": mac}
                        )
                    results.append(data)

                else:
                    logger.info(
                        "Please make sure to provide a supported --scantype"
                        " (nmap or fping), exiting process .."
                    )
                    exit()

            insert_subnet(results)

        # IPD MAIN PROCESS

        if options["network"]:
            try:
                subnet = options["network"][0]
                logger.debug(f"Scanning network: {subnet}")
                logger.debug(
                    f"Scan type:"
                    f" {options['scantype'][0] if options['scantype'] else 'None'}"
                )
                logger.debug(
                    f"Network tag:"
                    f" {options['nettag'][0] if options['nettag'] else 'None'}"
                )
                logger.debug(
                    f"Network name:"
                    f" {options['name'][0] if options['name'] else 'None'}"
                )
                logger.debug(
                    f"Network description:"
                    f"{options['description'][0] if options['description'] else 'None'}"
                )

                # building dicts for this subnet
                network, nettag, name, description = {}, {}, {}, {}
                # assign key to dict
                network[subnet] = subnet
                nettag[subnet] = options["nettag"][0] if options["nettag"] else None
                name[subnet] = options["name"][0] if options["name"] else None
                if options["description"]:
                    description[subnet] = options["description"][0]
                else:
                    description[subnet] = options["description"] = None

                ipd_scan_subnet(options["scantype"], network, nettag, name, description)
                logger.info("IpDiscover scan ran successfully.")
            except CommandError as e:
                logger.error(f"IpDiscover failed: {str(e.__cause__)}")

        elif options["file"]:
            logger.info(f"Importing networks from file: {options['file']}")
            logger.debug(
                f"Scan type for imported networks:"
                f" {options['scantype'][0] if options['scantype'] else 'None'}"
            )
            try:
                from_file(options["file"])
                ipd_scan_subnet(
                    options["scantype"],
                    options["network"],
                    options["nettag"],
                    options["name"],
                    options["description"],
                )
                logger.info("IpDiscover scan ran successfully.")
            except CommandError as e:
                logger.error(f"IpDiscover failed: {str(e.__cause__)}")

        elif options["list"]:
            logger.debug("Listing all discovered networks")
            output = "Already discovered subnets : \n"
            for subnet in ipd_list():
                nettag = subnet["nettag"]
                netid = subnet["netid"]
                mask = subnet["mask"]
                name = subnet["name"]
                description = subnet["description"] if subnet["description"] else "None"
                location = subnet["location"] if subnet["location"] else "None"
                # concatenate all data to display
                output += (
                    "Subnet "
                    + nettag
                    + " ("
                    + netid
                    + "/"
                    + mask
                    + ")"
                    + " - name : "
                    + name
                    + " - description : "
                    + description
                    + " - location : "
                    + location
                    + "\n"
                )
            logger.info(output)
