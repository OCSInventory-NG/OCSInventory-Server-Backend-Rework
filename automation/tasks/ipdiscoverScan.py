import csv
import logging
import os
import shutil
import subprocess
from ipaddress import AddressValueError, IPv4Network

import nmap
from automation.tasks.abstractTask import AbstractTask
from config.models import Config
from django.db import DatabaseError
from ipdiscover.netdevice.models import Netdevice
from ipdiscover.network.models import Network

logger = logging.getLogger("mgmt.management.commands.IpDiscover")


class IpDiscoverScan(AbstractTask):
    """
    IpDiscover class
    Automation task handling network discovery scans
    Scans networks using nmap or fping based on the configuration
    """

    def __init__(self):
        """Initialize with default scan type"""
        self.default_scantype = "nmap"
        self.subnets_list = None
        self.csv_file = None

    def execute(self):
        """
        - read configuration
        - get networks to scan (from config subnets_list or csv_file)
        - for each network, perform scan
        - update network and netdevices in database
        """
        try:
            logger.info("Starting IpDiscover task")

            # read configuration
            config = self.get_config()
            if not config:
                logger.warning(
                    "IpDiscover configuration not found or disabled"
                )
                return

            scantype = config.get("scantype", "nmap")
            self.default_scantype = scantype
            self.subnets_list = config.get("subnets_list", "")
            self.csv_file = config.get("csv_file", "")

            # check system requirements
            self.check_privileges()
            self.check_scan_tools(scantype)

            # determine networks to scan
            networks_to_scan = self.get_networks_to_scan()

            if not networks_to_scan:
                return

            total_networks = len(networks_to_scan)
            logger.info(f"Found {total_networks} networks to scan")

            processed = 0
            failed = 0

            for index, network_data in enumerate(networks_to_scan, 1):
                try:
                    nettag = network_data.get(
                        "nettag", network_data.get("network", "unknown")
                    )
                    logger.debug(
                        f"Processing network {index}/{total_networks}:"
                        f" {nettag}"
                    )
                    self.scan_network_data(network_data)
                    processed += 1
                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Failed to scan network: {e}",
                        exc_info=True,
                    )

            logger.info(
                f"IpDiscover task completed: {processed} succeeded,"
                f" {failed} failed out of {total_networks} total networks"
            )
        except Exception as e:
            logger.error(
                f"Critical error in IpDiscover task: {e}", exc_info=True
            )
            raise

    def get_config(self):
        """
        Get ipdiscover configuration from database

        Returns:
            dict: Configuration values or None if not found/disabled
        """
        try:
            logger.debug("Fetching ipdiscover configuration")
            ipdiscover_conf = Config.objects.filter(name="ipdiscover").first()
            if not ipdiscover_conf:
                logger.warning("IpDiscover config not found")
                return None

            config_dict = {}
            # ipdiscover config has nested structure
            for config_group in ipdiscover_conf.value:
                for item in config_group:
                    config_dict[item["name"]] = item["value"]

            # check if ipdiscover is enabled
            if not config_dict.get("ipdiscover", False):
                logger.info("IpDiscover is disabled in configuration")
                return None

            logger.debug(f"IpDiscover configuration: {config_dict}")
            return config_dict
        except DatabaseError as e:
            logger.error(
                f"Database error while fetching config: {e}", exc_info=True
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error while fetching config: {e}", exc_info=True
            )
            return None

    def check_privileges(self):
        """
        Check if running with elevated privileges
        """
        try:
            if hasattr(os, "geteuid"):
                if os.geteuid() != 0:
                    logger.info(
                        "Running this command as unprivileged user will not"
                        " provide optimal results. Consider running as root"
                        " instead."
                    )
        except Exception as e:
            logger.debug(f"Could not check privileges: {e}")

    def check_scan_tools(self, scantype):
        """
        Check if required scan tools (nmap or fping) are available
        """
        if scantype == "nmap":
            if not shutil.which("nmap"):
                logger.warning(
                    "nmap is not installed or not found in PATH."
                    " Network scans will fail."
                )
            else:
                logger.debug("nmap found in system PATH")
        elif scantype in ["fping", "ping"]:
            if not shutil.which("fping"):
                logger.warning(
                    "fping is not installed or not found in PATH."
                    " Network scans will fail."
                )
            else:
                logger.debug("fping found in system PATH")

    def get_networks_to_scan(self):
        """
        Get list of networks to scan based on configuration
        """
        networks_to_scan = []

        # priority: CSV file > subnets_list
        if self.csv_file:
            logger.info(f"Reading networks from CSV file: {self.csv_file}")
            networks_to_scan = self.parse_csv_file(self.csv_file)
        elif self.subnets_list:
            logger.info(f"Parsing subnets from list: {self.subnets_list}")
            networks_to_scan = self.parse_subnets_list(self.subnets_list)
        else:
            logger.warning(
                "No subnets configured: neither csv_file nor subnets_list"
                " is set. Exiting without performing scan."
            )
            networks_to_scan = []

        return networks_to_scan

    def parse_subnets_list(self, subnets_str):
        """
        Parse comma-separated list of subnets in CIDR notation
        """
        networks = []
        if not subnets_str or not subnets_str.strip():
            return networks

        subnet_list = [s.strip() for s in subnets_str.split(",") if s.strip()]
        logger.debug(f"Parsing {len(subnet_list)} subnets from list")

        for subnet_cidr in subnet_list:
            try:
                network_data = self.cidr_to_network_data(subnet_cidr)
                networks.append(network_data)
            except Exception as e:
                logger.error(
                    f"Error parsing subnet {subnet_cidr}: {e}",
                    exc_info=True,
                )

        return networks

    def parse_csv_file(self, file_path):
        """
        Import targeted subnets from CSV file
        """
        logger.debug(f"Reading CSV file: {file_path}")
        static_fields = ["network", "nettag", "name", "description"]
        imported_fields = []
        networks = []
        network_dict = {}

        try:
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if "network" in row:
                        logger.debug(f"Found header row: {row}")
                        for field in row:
                            imported_fields.append(field)
                            network_dict[field] = {}
                    else:
                        logger.debug(f"Processing network row: {row}")
                        if len(row) > 0:
                            network = row[0]
                            for idx, field in enumerate(imported_fields):
                                if idx < len(row):
                                    network_dict[field][network] = row[idx]

            if not set(static_fields) == set(imported_fields):
                missing_fields = set(static_fields) - set(imported_fields)
                logger.error(
                    f"Missing required fields in CSV: {missing_fields}"
                )
                return []

            # convert dict structure to list of network data
            for network_cidr in network_dict.get("network", {}).keys():
                try:
                    network_data = self.cidr_to_network_data(network_cidr)
                    # override with CSV values
                    name_dict = network_dict.get("name", {})
                    network_data["name"] = name_dict.get(
                        network_cidr, network_data["name"]
                    )
                    desc_dict = network_dict.get("description", {})
                    network_data["description"] = desc_dict.get(
                        network_cidr, network_data["description"]
                    )
                    # handle nettag: if provided, use ip:tag format
                    nettag_dict = network_dict.get("nettag", {})
                    csv_tag = nettag_dict.get(network_cidr, "")
                    if csv_tag and csv_tag.strip():
                        net_obj = IPv4Network(network_cidr, strict=False)
                        ip = str(net_obj.network_address)
                        network_data["nettag"] = ip + ":" + csv_tag
                    else:
                        # use default (ip)
                        network_data["nettag"] = network_data["nettag"]
                    networks.append(network_data)
                except Exception as e:
                    logger.error(
                        f"Error processing network {network_cidr}"
                        f" from CSV: {e}",
                        exc_info=True,
                    )

            logger.info(
                f"Successfully parsed {len(networks)} networks from CSV"
            )
            return networks

        except FileNotFoundError:
            logger.error(f"CSV file not found: {file_path}")
            return []
        except Exception as e:
            logger.error(
                f"Error reading CSV file: {str(e)}", exc_info=True
            )
            return []

    def cidr_to_network_data(self, cidr):
        """
        Convert CIDR notation to network data structure
        """
        try:
            net = IPv4Network(cidr, strict=False)
            netid = str(net.network_address)
            mask = str(net.netmask)
            ip = str(net.network_address)

            # extract nettag from CIDR (use ip as default)
            nettag = ip

            network_data = {
                "network": str(cidr),
                "nettag": nettag,
                "name": ip,
                "description": "",
                "netid": netid,
                "mask": mask,
            }

            return network_data
        except AddressValueError as e:
            logger.error(f"Invalid CIDR notation {cidr}: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Error converting CIDR {cidr} to network data: {e}",
                exc_info=True,
            )
            raise

    def get_all_networks_from_db(self):
        """
        Get all networks from database and convert to network data format
        """
        try:
            logger.debug("Fetching all networks from database")
            networks = Network.objects.all()
            if not networks.exists():
                logger.warning("No networks found in the database")
                return []

            network_list = []
            for network in networks:
                try:
                    cidr = self.network_to_cidr(network)
                    network_data = {
                        "network": cidr,
                        "nettag": network.nettag,
                        "name": network.name,
                        "description": network.description or "",
                        "netid": str(network.netid),
                        "mask": str(network.mask),
                    }
                    network_list.append(network_data)
                except Exception as e:
                    logger.error(
                        f"Error converting network {network.nettag}: {e}",
                        exc_info=True,
                    )

            return network_list
        except DatabaseError as e:
            logger.error(
                f"Database error while fetching networks: {e}", exc_info=True
            )
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error while fetching networks: {e}", exc_info=True
            )
            return []

    def scan_network_data(self, network_data):
        """
        Scan a single network and update database
        """
        try:
            cidr = network_data["network"]
            logger.debug(
                f"Scanning network {network_data['nettag']} with CIDR: {cidr}"
            )

            # prepare subnet data structure
            subnet_data = {
                "nettag": network_data["nettag"],
                "name": network_data["name"],
                "description": network_data.get("description", ""),
                "netid": network_data["netid"],
                "mask": network_data["mask"],
                "netdevices": [],
            }

            # perform scan
            if (
                self.default_scantype == "fping"
                or self.default_scantype == "ping"
            ):
                logger.debug(f"Scanning subnet {cidr} with fping ..")
                result = self.fping_scan(cidr)
                for device in result:
                    netname = ""
                    mac = device
                    subnet_data["netdevices"].append(
                        {"ip": device, "netname": netname, "mac": mac}
                    )
            elif self.default_scantype == "nmap":
                logger.debug(f"Scanning subnet {cidr} with nmap ..")
                result = self.nmap_scan(cidr)
                for device in result:
                    netname = ""
                    if (
                        "hostnames" in result[device]
                        and len(result[device]["hostnames"]) > 0
                    ):
                        netname = result[device]["hostnames"][0]["name"]
                    if "mac" not in result[device]["addresses"]:
                        mac = device
                    else:
                        mac = result[device]["addresses"]["mac"]
                    subnet_data["netdevices"].append(
                        {"ip": device, "netname": netname, "mac": mac}
                    )
            else:
                logger.error(
                    f"Unsupported scan type: {self.default_scantype}."
                    f" Supported types: nmap, fping"
                )
                return

            # insert/update subnet and netdevices
            self.insert_subnet([subnet_data])

            logger.info(
                f"Successfully scanned network {network_data['nettag']}"
            )
        except Exception as e:
            logger.error(
                f"Error scanning network: {e}", exc_info=True
            )
            raise

    def network_to_cidr(self, network):
        """
        Convert Network model to CIDR notation
        """
        try:
            netid = str(network.netid)
            mask = str(network.mask)

            # convert mask to prefix length
            net = IPv4Network(f"{netid}/{mask}", strict=False)
            return str(net)
        except AddressValueError as e:
            logger.error(
                f"Invalid network configuration for {network.nettag}:"
                f" netid={network.netid}, mask={network.mask}. Error: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Error converting network {network.nettag} to CIDR: {e}",
                exc_info=True,
            )
            raise

    def fping_scan(self, net):
        """Scan devices present on specific subnet and return their ip
         addresses if alive
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

    def nmap_scan(self, net):
        """Scan devices present on specific submet and return their ip
         addresses and mac addresses if available
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

    def insert_netdevices(self, subnet, network_id):
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

    def insert_subnet(self, subnets):
        """Insert subnets and related netdevices into database
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
                    self.insert_netdevices(subnet, subnet_obj)
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
                    self.insert_netdevices(subnet, subnet_obj)
                except Exception as e:
                    logger.error(
                        f"Error while creating subnet"
                        f" {subnet['nettag']}: {str(e)}"
                    )
