# Wires the API above to /sampleextension/comments/ once the extension is
# enabled (see ocsinventory_backend/urls.py, which mounts this file).

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SampleCommentViewSet

router = DefaultRouter()
router.register(r"comments", SampleCommentViewSet, basename="samplecomment")

urlpatterns = [
    path("", include(router.urls)),
]
