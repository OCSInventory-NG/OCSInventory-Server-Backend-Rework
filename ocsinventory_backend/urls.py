"""ocsinventory_backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from accountinfo.routers import AccountinfoRouter
from asset.agent_config.routers import AgentConfigRouter
from asset.asset_group.routers import AssetGroupRouter
from asset.collection.views import CollectionView
from asset.inventory_base.routers import InventoryBaseRouter
from asset.inventory_field.routers import InventoryFieldRouter
from asset.inventory_section.routers import InventorySectionRouter
from asset.legacy.views import LegacyView
from asset.log.routers import LogRouter
from auth.auth_config.routers import AuthConfigRouter
from auth.auth_mapping.routers import AuthMappingRouter
from auth.auth_method.routers import AuthMethodRouter
from auth.auth_view.auth_views import BaseAuthView, CallbackView
from automation.history.routers import HistoryRouter
from automation.rule.routers import RuleRouter
from automation.scheduler.routers import SchedulerRouter
from config.routers import ConfigRouter
from dashboard.chart.routers import DashboardChartRouter
from dashboard.layout.routers import DashboardLayoutRouter
from deployment.action.routers import ActionRouter
from deployment.package.routers import PackageRouter
from deployment.result.routers import ResultRouter
from django.conf.urls.static import static

# Base import to get API Working
from django.urls import include, path
from extension.routers import ExtensionRouter
from filemanager.routers import FileManagerRouter
from group.routers import GroupRouter
from inventory.category.routers import CategoryRouter
from inventory.field.routers import FieldRouter
from inventory.section.routers import SectionRouter
from inventory.software.routers import SoftwareRouter
from inventory.template.routers import TemplateRouter
from ipdiscover.netdevice.routers import NetdeviceRouter
from ipdiscover.netgroup.routers import NetgroupRouter
from ipdiscover.network.routers import NetworkRouter
from ocsinventory_backend import settings
from ocsinventory_backend.ocs_framework.viewsets import ApiCheckViewSet

# Import dedicated routers and provide different endpoint
from permission.routers import PermissionRouter
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter
from search.routers import SearchRouter
from search.views import SearchView
from snmp.scanner.routers import SnmpScannerRouter
from snmp.snmp_config.routers import SnmpConfigRouter
from user.routers import UserRouter

import sys

# Routers provide a way of automatically determining the URL conf.
defaultRouter = DefaultRouter()

# Automation scheduler
schedulerRouter = SchedulerRouter()
schedulerRouter = schedulerRouter.defineRoutes(defaultRouter)

# Automation History
historyRouter = HistoryRouter()
historyRouter = historyRouter.defineRoutes(defaultRouter)

# Automation Rule
ruleRouter = RuleRouter()
ruleRouter = ruleRouter.defineRoutes(defaultRouter)


# Add agentConfigRouter declaration
agentConfigRouter = AgentConfigRouter()
agentConfigRouter = agentConfigRouter.defineRoutes(defaultRouter)

# Add permissionsRouter declaration
permissionRouter = PermissionRouter()
permissionRouter = permissionRouter.defineRoutes(defaultRouter)

# Add userRouter declaration
userRouter = UserRouter()
userRouter = userRouter.defineRoutes(defaultRouter)

# Add groupRouter declaration
groupRouter = GroupRouter()
groupRouter = groupRouter.defineRoutes(defaultRouter)

# Add configRouter declaration
configRouter = ConfigRouter()
configRouter = configRouter.defineRoutes(defaultRouter)

# Add templateRouter declaration
tplRouter = TemplateRouter()
tplRouter = tplRouter.defineRoutes(defaultRouter)

# Add sectionRouter declaration
sectionRouter = SectionRouter()
sectionRouter = sectionRouter.defineRoutes(defaultRouter)

# Add fieldRouter declaration
fieldRouter = FieldRouter()
fieldRouter = fieldRouter.defineRoutes(defaultRouter)

# Add categoryRouter declaration
categoryRouter = CategoryRouter()
categoryRouter = categoryRouter.defineRoutes(defaultRouter)

# Add software router declaration
softwareRouter = SoftwareRouter()
softwareRouter = softwareRouter.defineRoutes(defaultRouter)

# Add Netdevicce declaration
netrouter = NetdeviceRouter()
netrouter = netrouter.defineRoutes(defaultRouter)

# Add Netdevicce declaration
netrouter = NetworkRouter()
netrouter = netrouter.defineRoutes(defaultRouter)

# Add Netdevicce declaration
netrouter = NetgroupRouter()
netrouter = netrouter.defineRoutes(defaultRouter)

# Add SnmpScanner declaration
snmpScannerRouter = SnmpScannerRouter()
snmpScannerRouter = snmpScannerRouter.defineRoutes(defaultRouter)

# Add SnmpConfig declaration
snmpConfigRouter = SnmpConfigRouter()
snmpConfigRouter = snmpConfigRouter.defineRoutes(defaultRouter)

# Add logRouter declaration
logRouter = LogRouter()
logRouter = logRouter.defineRoutes(defaultRouter)

# Add inventoryBaseRouter declaration
inventoryBaseRouter = InventoryBaseRouter()
inventoryBaseRouter = inventoryBaseRouter.defineRoutes(defaultRouter)

# Add inventorySectionRouter declaration
inventorySectionRouter = InventorySectionRouter()
inventorySectionRouter = inventorySectionRouter.defineRoutes(defaultRouter)

# Add inventoryFieldRouter declaration
inventoryFieldRouter = InventoryFieldRouter()
inventoryFieldRouter = inventoryFieldRouter.defineRoutes(defaultRouter)

# Add accountinfo declaration
accountinfoRouter = AccountinfoRouter()
accountinfoRouter = accountinfoRouter.defineRoutes(defaultRouter)

# Add package declaration
packageRouter = PackageRouter()
packageRouter = packageRouter.defineRoutes(defaultRouter)

# Add action declaration
actionRouter = ActionRouter()
actionRouter = actionRouter.defineRoutes(defaultRouter)

# Add result declaration
resultRouter = ResultRouter()
resultRouter = resultRouter.defineRoutes(defaultRouter)

# Add authConfig declaration
authConfigRouter = AuthConfigRouter()
authConfigRouter = authConfigRouter.defineRoutes(defaultRouter)

# Add authMethod declaration
authMethodRouter = AuthMethodRouter()
authMethodRouter = authMethodRouter.defineRoutes(defaultRouter)

# Add authMapping declaration
authMappingRouter = AuthMappingRouter()
authMappingRouter = authMappingRouter.defineRoutes(defaultRouter)

# Add search declaration
searchRouter = SearchRouter()
searchRouter = searchRouter.defineRoutes(defaultRouter)

# Add AssetGroup declaration
assetGroupRouter = AssetGroupRouter()
assetGroupRouter = assetGroupRouter.defineRoutes(defaultRouter)

# Add Dashboard layout declaration
dashboardRouter = DashboardLayoutRouter()
dashboardRouter = dashboardRouter.defineRoutes(defaultRouter)

# Add Dashboard chart declaration
dashboardChartRouter = DashboardChartRouter()
dashboardChartRouter = dashboardChartRouter.defineRoutes(defaultRouter)

# Add FileManager declaration
fileManagerRouter = FileManagerRouter()
fileManagerRouter = fileManagerRouter.defineRoutes(defaultRouter)

# Add Extension declaration
extensionRouter = ExtensionRouter()
extensionRouter = extensionRouter.defineRoutes(defaultRouter)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path(r"", include(defaultRouter.urls)),
    path("api-check/", ApiCheckViewSet.as_view({"get": "api_check"}), name="api_check"),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("api-auth/token", obtain_auth_token, name="api_token_auth"),
    path("asset/collection/", CollectionView.as_view(), name="asset_collection"),
    path("asset/legacy/", LegacyView.as_view(), name="legacy_collection"),
    path("search/", SearchView.as_view(), name="search"),
    # Authentication
    path("login/", BaseAuthView.as_view(), name="login"),
    path("callback/", CallbackView.as_view(), name="callback"),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

def _should_skip_dynamic_extension_urls():
    # avoid DB access during certain commands
    return any(cmd in sys.argv for cmd in ["migrate", "makemigrations", "collectstatic", "test"])

if not _should_skip_dynamic_extension_urls():
    try:
        from extension.models import Extension
        from django.db.utils import OperationalError, ProgrammingError

        for ext in Extension.objects.filter(enabled=True):
            app_path = f"extensions.{ext.django_app}" or f"extensions.{ext.name}"
            try:
                urlpatterns.append(path(f"{ext.django_app}/", include(f"{app_path}.urls")))
                print(urlpatterns)
            except ModuleNotFoundError:
                continue

    except (OperationalError, ProgrammingError):
        pass


