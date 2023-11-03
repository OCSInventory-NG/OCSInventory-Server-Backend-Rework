from rest_framework import serializers
from django.db.models import F

from .models import AuthMethod


class AuthMethodSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthMethod
        fields = '__all__'

    def validate(self, data):
        """
        Validate the data before updating the object
        Two checks are performed:
        - If auth_type=SSO, only one method can be enabled
        - If auth_type=OTHER, PRIORITY must be unique

        NB: greater priority number = lower priority (1 is highest priority)
        """
        # PUT will trigger the below but also PATCH made on 'enabled' or 'priority'
        if data.get('enabled') or data.get('priority'):
            # partial update: get the current auth_type
            if self.instance:
                data['auth_type'] = data.get('auth_type', self.instance.auth_type)

            # check if TYPE=SSO and enforce only one method enabled
            if data.get('auth_type') == 'SSO' and data.get('enabled'):
                existing_sso = AuthMethod.objects.filter(
                    auth_type='SSO', enabled=True
                ).exclude(pk=self.instance.pk if self.instance else None)
                if existing_sso.exists():
                    raise serializers.ValidationError(
                        "Another SSO method is already enabled. "
                        "Please disable it before enabling a new one."
                    )

            # check PRIORITY uniqueness for non-SSO methods
            if data.get('auth_type') != 'SSO' and data.get('priority') is not None:
                priority = data.get('priority')
                # Check if there is an existing method with the same priority
                existing_method = AuthMethod.objects.filter(
                    priority=priority
                ).exclude(auth_type='SSO').exclude(pk=self.instance.pk if self.instance
                                                   else None).first()

                if existing_method:
                    # if the current priority is being updated to a higher priority
                    if self.instance and priority < self.instance.priority:
                        # decrease the priority of all methods with lower priority
                        AuthMethod.objects.filter(
                            priority__lt=self.instance.priority,
                            priority__gte=priority
                        ).exclude(auth_type='SSO').update(priority=F('priority') + 1)

                    # if the current priority is being updated to a lower priority
                    elif self.instance and priority > self.instance.priority:
                        # increase the priority of all methods with higher priority
                        AuthMethod.objects.filter(
                            priority__lte=priority,
                            priority__gt=self.instance.priority
                        ).exclude(auth_type='SSO').update(priority=F('priority') - 1)

                    # if adding a new method or changing priority
                    else:
                        # decrease the priority of all methods with priority equal to
                        # or higher than the current one
                        AuthMethod.objects.filter(
                            priority__gte=priority
                        ).exclude(auth_type='SSO').update(priority=F('priority') + 1)

        return data
