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
from asset.base.routers import BaseRouter
from config.routers import ConfigRouter

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
from user.routers import UserRouter

# Routers provide a way of automatically determining the URL conf.
defaultRouter = DefaultRouter()

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

# Add baseRouter declaration
baseRouter = BaseRouter()
baseRouter = baseRouter.defineRoutes(defaultRouter)

# Add accountinfo declaration
accountinfoRouter = AccountinfoRouter()
accountinfoRouter = accountinfoRouter.defineRoutes(defaultRouter)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("api-auth/token", obtain_auth_token, name="api_token_auth"),
]
