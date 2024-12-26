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
    allowed_methods = ["get"]
    queryset = InventoryBase.objects.all()
    serializer_class = None

    def list(self, request):
        """
        Return the list of available charts.
        """
        data = [
            {
                "category": "asset",
                "name": "total_ALL",
                "description": "Total devices count",
                "charttype": "Counter",
            },
            {
                "category": "asset",
                "name": "total_WIN",
                "description": "Total Windows devices count",
                "charttype": "Counter",
            },
            {
                "category": "asset",
                "name": "total_LIN",
                "description": "Total Linux devices count",
                "charttype": "Counter",
            },
            {
                "category": "asset",
                "name": "total_MAC",
                "description": "Total MacOS devices count",
                "charttype": "Counter",
            },
            {
                "category": "asset",
                "name": "total_LEG",
                "description": "Total Legacy devices count",
                "charttype": "Counter",
            },
            {
                "category": "asset",
                "name": "total_SNMP",
                "description": "Total SNMP devices count",
                "charttype": "Counter",
            },
            {
                "category": "asset",
                "name": "oscount",
                "description": "Unique OS names and their count",
                "charttype": "DonutChart",
            },
            {
                "category": "asset",
                "name": "lastcontacted",
                "description": "Devices per last contacted date (7 days)",
                "charttype": "LineChart",
            },
            {
                "category": "network",
                "name": "nb_netdevices",
                "description": "Total netdevices count",
                "charttype": "Counter",
            },
            {
                "category": "network",
                "name": "nb_networks",
                "description": "Total networks count",
                "charttype": "Counter",
            },
            {
                "category": "network",
                "name": "networks",
                "description": "Unique network names and their devices count",
                "charttype": "BarChart",
            },
        ]

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="total_ALL")
    def return_total_all(self, request):
        try:
            total_data = self.get_total("ALL")
            return Response(total_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="total_WIN")
    def return_total_win(self, request):
        try:
            total_data = self.get_total("WIN")
            return Response(total_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="total_LIN")
    def return_total_lin(self, request):
        try:
            total_data = self.get_total("LIN")
            return Response(total_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="total_MAC")
    def return_total_mac(self, request):
        try:
            total_data = self.get_total("MAC")
            return Response(total_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="total_LEG")
    def return_total_leg(self, request):
        try:
            total_data = self.get_total("LEG")
            return Response(total_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="total_SNMP")
    def return_total_snmp(self, request):
        try:
            total_data = self.get_total("SNMP")
            return Response(total_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="nb_netdevices")
    def return_nb_netdevices(self, request):
        try:
            netdevices = Netdevice.objects.all()
            netdevices_data = {"total": netdevices.count()}
            return Response(netdevices_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="nb_networks")
    def return_nb_networks(self, request):
        try:
            networks = Network.objects.all()
            network_data = {"total": networks.count()}
            return Response(network_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_total(self, os_template):
        """
        Return the total count of devices per OS family
        """

        try:
            # could remove the template is null if we want to count
            # all the InventoryBase objects whether they are linked
            # to a template or not
            data = self.queryset.filter()
            count = 0

            # timeframe for contacted is today
            since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            contacted_data = self.queryset.filter(last_update__gte=since)
            contacted = 0

            if "ALL" == os_template:
                count = data.count()
                contacted = contacted_data.filter().count()
            if "WIN" == os_template:
                count = data.filter(template__os="WIN").count()
                contacted = contacted_data.filter(template__os="WIN").count()
            if "LIN" == os_template:
                count = data.filter(template__os="LIN").count()
                contacted = contacted_data.filter(template__os="LIN").count()
            if "MAC" == os_template:
                count = data.filter(template__os="MAC").count()
                contacted = contacted_data.filter(template__os="MAC").count()
            if "LEG" == os_template:
                count = data.filter(template__os="LEG").count()
                contacted = contacted_data.filter(template__os="LEG").count()
            if "SNMP" == os_template:
                count = data.filter(osname="SNMP").count()
                contacted = contacted_data.filter(osname="SNMP").count()

            total_data = {"total": count, "contacted": contacted}

            return total_data
        except Exception as e:
            msg = f"Error in total count: {e}"
            self.logger.error(msg)
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="oscount")
    def get_os(self, request):
        """
        Return unique OS names and their associated count
        """
        try:
            data = self.queryset.filter()

            os_counters = {}
            for device in data:
                os_counters[device.osname] = os_counters.get(device.osname, 0) + 1

            os_data = {
                "options": {"labels": list(os_counters.keys())},
                "series": list(os_counters.values()),
            }
            return Response(os_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in OS count: {e}"
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="lastcontacted")
    def get_last_contacted(self, request):
        """
        Return the count of devices per last contacted date
        """
        try:
            # timeframe for contacted is seven days from the current date
            since = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=7)
            contacted = self.queryset.filter(last_update__gte=since)

            last_contacted_counters = {}
            for device in contacted:
                date_str = device.last_update.strftime("%Y-%m-%d")
                last_contacted_counters[date_str] = (
                    last_contacted_counters.get(date_str, 0) + 1
                )

            last_contacted_data = {
                "options": {
                    "chart": {"id": "last-contacted-chart"},
                    "xaxis": {
                        "categories": list(last_contacted_counters.keys()),
                        "convertedCatToNumeric": True,
                    },
                },
                "series": [
                    {"name": "Assets", "data": list(last_contacted_counters.values())}
                ],
            }
            return Response(last_contacted_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in last contacted : {e}"
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="networks")
    def get_devices_per_network(self, request):
        """
        Return the count of devices per network
        """
        try:
            data = Netdevice.objects.all()

            netdevices_counters = {}
            for device in data:
                netdevices_counters[device.network.name] = (
                    netdevices_counters.get(device.network.name, 0) + 1
                )

            network_data = {
                "options": {
                    "chart": {"id": "network-chart"},
                    "xaxis": {
                        "categories": list(netdevices_counters.keys()),
                        "convertedCatToNumeric": False,
                        "position": "top",
                    },
                },
                "series": [
                    {"name": "Devices", "data": list(netdevices_counters.values())}
                ],
            }
            return Response(network_data, status=status.HTTP_200_OK)
        except Exception as e:
            msg = f"Error in netdevices : {e}"
            return Response(
                {"error": msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def os_repartition(self, data):
        """
        Return the count of devices for each OS
        """
        try:
            windows = data.filter(template__os="WIN").count()
            linux = data.filter(template__os="LIN").count()
            macos = data.filter(template__os="MAC").count()
            snmp = data.filter(template__os="SNMP").count()

            return windows, linux, macos, snmp
        except Exception as e:
            raise APIException(f"Error in OS repartition: {e}")
