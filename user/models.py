from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from automation.rule.logic import Logic



@receiver(post_save, sender=User)
def user_login_handler(sender, instance, created, **kwargs):
    """
    Signal handler for user login.
    """
    if not getattr(instance, 'processed', False):
        logic = Logic('user_login', instance)
        instance = logic.process_rules()

