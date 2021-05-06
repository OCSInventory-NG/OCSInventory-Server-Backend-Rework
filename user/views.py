from django.contrib.auth.models import User
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from user.serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    permission_classes = [IsAuthenticated] # Need to be authenticated to consult

    queryset = User.objects.all()
    serializer_class = UserSerializer
