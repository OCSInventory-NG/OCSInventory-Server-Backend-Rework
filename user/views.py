from django.contrib.auth.models import User
from rest_framework import viewsets
from user.serializers import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer