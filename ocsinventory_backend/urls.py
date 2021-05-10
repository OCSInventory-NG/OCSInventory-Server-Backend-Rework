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

# Base import to get API Working
from django.urls import path, include
from django.contrib.auth.models import User
from rest_framework import serializers, viewsets
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token


# Import dedicated routers and provide different endpoint
from user.routers import UserRouter
from group.routers import GroupRouter

# Routers provide a way of automatically determining the URL conf.
defaultRouter = DefaultRouter()

# Add userRoute declaration
userRouter = UserRouter()
userRouter = userRouter.defineRoutes(defaultRouter)

# Add groupRoute declaration
groupRouter = GroupRouter()
groupRouter = groupRouter.defineRoutes(defaultRouter)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api-auth/token', obtain_auth_token, name='api_token_auth'),
]

# Add URL Patterns comming from routers
urlpatterns += userRouter.urls
