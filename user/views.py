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

    # Need to be authenticated to consult
    permission_classes = [IsAuthenticated]

    queryset = User.objects.all()
    serializer_class = UserSerializer
