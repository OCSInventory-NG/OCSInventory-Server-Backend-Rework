from datetime import datetime, timedelta
from asset.inventory_base.models import InventoryBase
from dashboard.chart.models import DashboardChart
from dashboard.chart.serializers import DashboardChartSerializer
from ipdiscover.netdevice.models import Netdevice
from ipdiscover.network.models import Network
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status


class DashboardChartViewSet(viewsets.OCSViewSet):
    """
    This class allows the frontend to request data for the dashboard charts
    """

    filter_backends = []
    permission_classes = [DefaultModelPermissions]
    queryset = InventoryBase.objects.all()
    serializer_class = DashboardChartSerializer
    model = DashboardChart

    # TODO : pre define response formats for each type of chart ?

    @action(detail=False, methods=['get'], url_path='total')
    def get_total(self, request):
        """
        Return the total count of devices per OS family
        """
        # could remove the template is null if we want to count
        # all the InventoryBase objects whether they are linked
        # to a template or not
        data = InventoryBase.objects.filter(template__isnull=False)
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

    @action(detail=False, methods=['get'], url_path='contacted')
    def get_contacted(self, request):
        """
        Return the count of contacted devices today
        """
        # timeframe for contacted is today
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        contacted = InventoryBase.objects.filter(last_update__gte=since)
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

    @action(detail=False, methods=['get'], url_path='oscount')
    def get_os(self, request):
        """
        Return unique OS names and their associated count
        """
        data = InventoryBase.objects.all()

        os_counters = {}
        for device in data:
            if device.osname in os_counters:
                os_counters[device.osname] += 1
            else:
                os_counters[device.osname] = 1

        os_data = {
            "options": {
                "labels": list(os_counters.keys())
            },
            "series": list(os_counters.values())
        }
        return Response(os_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='lastcontacted')
    def get_last_contacted(self, request):
        """
        Return the count of devices per last contacted date
        """
        # timeframe for contacted is seven days from the current date
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
        contacted = InventoryBase.objects.filter(last_update__gte=since)

        last_contacted_counters = {}
        for device in contacted:
            if device.last_update in last_contacted_counters:
                last_contacted_counters[device.last_update.strftime('%Y-%m-%d')] += 1
            else:
                last_contacted_counters[device.last_update.strftime('%Y-%m-%d')] = 1

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

    @action(detail=False, methods=['get'], url_path='netdevices')
    def get_devices_per_network(self, request):
        """
        Return the count of devices per network
        """
        data = Netdevice.objects.all()

        netdevices_counters = {}
        for device in data:
            if device.network.name in netdevices_counters:
                netdevices_counters[device.network.name] += 1
            else:
                netdevices_counters[device.network.name] = 1

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
    
    @action(detail=False, methods=['get'], url_path='networks')
    def get_networks(self, request):
        """
        Return unique network names and their associated count
        """
        networks = Network.objects.all()
        netdevices = Netdevice.objects.all()

        network_counters = {}
        for network in networks:
            if network.name in network_counters:
                network_counters[network.name] += 1
            else:
                network_counters[network.name] = 1

        network_data = {
            "total": networks.count(),
            "names": list(network_counters.keys()),
            "devices": {
                "total": netdevices.count(),
            }
        }

        return Response(network_data, status=status.HTTP_200_OK)

    def os_repartition(self, data):
        """
        Return the count of devices for each OS
        """
        # filter the InventoryBase objects by the template os field
        windows = data.filter(template__os='WIN').count()
        linux = data.filter(template__os='LIN').count()
        macos = data.filter(template__os='MAC').count()
        snmp = data.filter(template__os='SNMP').count()

        return windows, linux, macos, snmp
