from automation.rule.logic import Logic
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


# user logged in signal
@receiver(user_logged_in, sender=User)
def user_login_handler(sender, user, request, **kwargs):
    """
    Signal handler for user login.
    """
    if not getattr(user, "processed", False):
        logic = Logic("user_login", user)
        user = logic.process_rules()
