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
from asset.collection.views import CollectionView
from asset.inventory_base.routers import InventoryBaseRouter
from asset.inventory_field.routers import InventoryFieldRouter
from asset.inventory_section.routers import InventorySectionRouter
from asset.log.routers import LogRouter
from auth.auth_config.routers import AuthConfigRouter
from auth.auth_mapping.routers import AuthMappingRouter
from auth.auth_method.routers import AuthMethodRouter
from auth.auth_view.auth_views import BaseAuthView, CallbackView
from automation.history.routers import HistoryRouter
from automation.rule.routers import RuleRouter
from automation.scheduler.routers import SchedulerRouter
from config.routers import ConfigRouter
from deployment.action.routers import ActionRouter
from deployment.package.routers import PackageRouter
from deployment.result.routers import ResultRouter

# Base import to get API Working
from django.urls import include, path
from group.routers import GroupRouter
from inventory.field.routers import FieldRouter
from inventory.section.routers import SectionRouter
from inventory.template.routers import TemplateRouter
from ipdiscover.netdevice.routers import NetdeviceRouter
from ipdiscover.netgroup.routers import NetgroupRouter
from ipdiscover.network.routers import NetworkRouter

# Import dedicated routers and provide different endpoint
from permission.routers import PermissionRouter
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter
from search.routers import SearchRouter
from search.views import SearchView
from asset.asset_group.routers import AssetGroupRouter
from user.routers import UserRouter

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

# Add Netdevicce declaration
netrouter = NetdeviceRouter()
netrouter = netrouter.defineRoutes(defaultRouter)

# Add Netdevicce declaration
netrouter = NetworkRouter()
netrouter = netrouter.defineRoutes(defaultRouter)

# Add Netdevicce declaration
netrouter = NetgroupRouter()
netrouter = netrouter.defineRoutes(defaultRouter)

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

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path(r"", include(defaultRouter.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("api-auth/token", obtain_auth_token, name="api_token_auth"),
    path("asset/collection/", CollectionView.as_view(), name="asset_collection"),
    path("search/", SearchView.as_view(), name="search"),
    # Authentication
    path("login/", BaseAuthView.as_view(), name="login"),
    path("callback/", CallbackView.as_view(), name="callback"),
]
