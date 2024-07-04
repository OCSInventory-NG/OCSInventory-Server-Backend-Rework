from datetime import datetime, timedelta
import logging
from asset.inventory_base.models import InventoryBase
from ipdiscover.netdevice.models import Netdevice
from ipdiscover.network.models import Network
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException


class DashboardChartViewSet(viewsets.OCSViewSet):
    """
    This class allows the frontend to request data for the dashboard charts
    """

    permission_classes = [DefaultModelPermissions]
    allowed_methods = ['get']
    queryset = InventoryBase.objects.all()
    serializer_class = None

    def list(self, request):
        """
        Return the list of available charts.
        """
        data = [
            {"name": "total", "description": "Total devices per OS family"},
            {"name": "contacted", "description": "Contacted devices today per OS family"},
            {"name": "oscount", "description": "Unique OS names and their count"},
            {"name": "lastcontacted", "description": "Devices per last contacted date (7 days)"},
            {"name": "netdevices", "description": "Devices per network"},
            {"name": "networks", "description": "Unique network names and their count"},
        ]

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='total')
    def get_total(self, request):
        """
        Return the total count of devices per OS family
        """
        try:
            # could remove the template is null if we want to count
            # all the InventoryBase objects whether they are linked
            # to a template or not
            data = self.queryset.filter(template__isnull=False)
            total = data.count()

            windows, linux, macos, snmp = self.os_repartition(data)
            total_data = {
                "total": total,
                "windows": windows,
                "linux": linux,
                "macos": macos,
                "snmp": snmp
            }

            return Response(total_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='contacted')
    def get_contacted(self, request):
        """
        Return the count of contacted devices today
        """
        try:
            # timeframe for contacted is today
            since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            contacted = self.queryset.filter(last_update__gte=since)
            total = contacted.count()
            # process is basically the same as get_total method
            windows, linux, macos, snmp = self.os_repartition(contacted)
            contacted_data = {
                "total": total,
                "windows": windows,
                "linux": linux,
                "macos": macos,
                "snmp": snmp,
            }
            return Response(contacted_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in contacted count: {e}"
            self.logger.error(msg)
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='oscount')
    def get_os(self, request):
        """
        Return unique OS names and their associated count
        """
        try:
            data = self.queryset

            os_counters = {}
            for device in data:
                os_counters[device.osname] = os_counters.get(device.osname, 0) + 1

            os_data = {
                "options": {
                    "labels": list(os_counters.keys())
                },
                "series": list(os_counters.values())
            }
            return Response(os_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in OS count: {e}"
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='lastcontacted')
    def get_last_contacted(self, request):
        """
        Return the count of devices per last contacted date
        """
        try:
            # timeframe for contacted is seven days from the current date
            since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
            contacted = self.queryset.filter(last_update__gte=since)

            last_contacted_counters = {}
            for device in contacted:
                date_str = device.last_update.strftime('%Y-%m-%d')
                last_contacted_counters[date_str] = last_contacted_counters.get(date_str, 0) + 1

            last_contacted_data = {
                "options": {
                    "chart": {
                        "id": "last-contacted-chart"
                    },
                    "xaxis": {
                        "categories": list(last_contacted_counters.keys()),
                        "convertedCatToNumeric": True
                    },
                },
                "series": [
                    {
                        "name": "Assets number",
                        "data": list(last_contacted_counters.values())
                    }
                ]
            }
            return Response(last_contacted_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in last contacted : {e}"
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='netdevices')
    def get_devices_per_network(self, request):
        """
        Return the count of devices per network
        """
        try:
            data = Netdevice.objects.all()

            netdevices_counters = {}
            for device in data:
                netdevices_counters[device.network.name] = netdevices_counters.get(device.network.name, 0) + 1

            network_data = {
                "options": {
                    "chart": {
                        "id": "network-chart"
                    },
                    "xaxis": {
                        "categories": list(netdevices_counters.keys()),
                        "convertedCatToNumeric": False
                    },
                },
                "series": [
                    {
                        "name": "Devices number",
                        "data": list(netdevices_counters.values())
                    }
                ]
            }
            return Response(network_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in netdevices : {e}"
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='networks')
    def get_networks(self, request):
        """
        Return unique network names and their associated count
        """
        try:
            networks = Network.objects.all()
            netdevices = Netdevice.objects.all()

            network_counters = {}
            for network in networks:
                network_counters[network.name] = network_counters.get(network.name, 0) + 1

            network_data = {
                "total": networks.count(),
                "names": list(network_counters.keys()),
                "devices": {
                    "total": netdevices.count(),
                }
            }

            return Response(network_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in networks : {e}"
            return Response({"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def os_repartition(self, data):
        """
        Return the count of devices for each OS
        """
        try:
            windows = data.filter(template__os='WIN').count()
            linux = data.filter(template__os='LIN').count()
            macos = data.filter(template__os='MAC').count()
            snmp = data.filter(template__os='SNMP').count()

            return windows, linux, macos, snmp
        except Exception as e:
            raise APIException(f"Error in OS repartition: {e}")
