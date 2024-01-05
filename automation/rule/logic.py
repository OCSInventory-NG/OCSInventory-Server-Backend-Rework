from accountinfo.models import AccountinfoData
from automation.rule.models import Rule
from json_logic import jsonLogic
from django.db.models.fields import CharField, IntegerField
from django.db.models.fields.json import JSONField
from django.db.models.fields.related import ForeignKey
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.db.models.fields.related import ManyToManyField

import logging


class Logic:
    """
    This class is used to process the rules
    Conditions are evaluated using JSON Logic (https://jsonlogic.com/)

    Actions are executed based on the result of the conditions

    Args:
        trigger (str): trigger name
        instance (object): instance of a model
    """

    LOGGER = logging.getLogger(__name__)

    def __init__(self, trigger, instance):
        self.trigger = trigger
        self.instance = instance

    def process_rules(self):
        """Process the rules for the given trigger using JSON Logic
        """
        rules = Rule.objects.filter(trigger=self.trigger, enabled=True)

        for rule in rules:
            try:
                result = jsonLogic(rule.logic, self.instance.__dict__)
                
                if result:
                    self.execute_actions(rule)
            except Exception as e:
                self.LOGGER.error(f"Error processing rule: {e}")


    def execute_actions(self, rule):
        """Execute the actions for the given rule
        """
        for action in rule.actions.all():
            if action.action == 'set':
                self.handle_set_action(action)
            else:
                self.LOGGER.error(f"Action not supported: {action.action}")

    def handle_set_action(self, action):
        """Handle the set action

        The presence of content_type and object_id indicates that the action
        must be executed on a related instance
        Otherwise, the action is executed on the instance itself
        """
        if action.content_type and action.object_id:
            try:
                model = action.content_type.model_class()
                related_instance = model.objects.get(id=action.object_id)
                self.update_field(related_instance, action)
            except model.DoesNotExist:
                self.LOGGER.error(f"Related instance not found: {model.__name__} with ID {action.object_id}")
            except Exception as e:
                self.LOGGER.error(f"Error updating related instance: {e}")
        else:
            try:
                self.update_field(self.instance, action)
            except Exception as e:
                self.LOGGER.error(f"Error updating instance: {e}")

    def update_field(self, instance, action):
        """Update the field of the given instance

        Difference is made between simple fields and JSON fields
        JSONField processing is experimental and attempts to update the
        data in nested JSON structures
        """
        if ':' in action.field:
            field, key = action.field.split(':', 1)
            self.update_json_field(instance, field, key, action.value)
        else:
            value = self.convert_value(instance, action.field, action.value)
            field = instance._meta.get_field(action.field)
            if isinstance(field, ManyToManyField):
                # Use set() for ManyToManyFields
                getattr(instance, action.field).add(value.id)
            else:
                setattr(instance, action.field, value)
        # setting processed to True to avoid infinite loop where .save() triggers the post_save signal
        instance.processed = True
        instance.save()

    @staticmethod
    def convert_value(instance, field_name, value):
        try:
            field = instance._meta.get_field(field_name)
            field_type = type(field)

            if field_type in [CharField, JSONField]:
                return str(value)
            elif field_type == IntegerField:
                return int(value)
            elif issubclass(field_type, ForeignKey):
                related_model = field.related_model
                try:
                    related_instance = related_model.objects.get(id=value)
                    return related_instance
                except ObjectDoesNotExist:
                    Logic.LOGGER.error(f"Related instance not found: {related_model.__name__} with ID {value}")
                    return None
                except ValueError:
                    Logic.LOGGER.error(f"Invalid value for related instance: {value}")
                    return None
            elif issubclass(field_type, ManyToManyField):
                related_model = field.related_model
                try:
                    related_instances = related_model.objects.get(id=value)
                    return related_instances
                except ObjectDoesNotExist:
                    Logic.LOGGER.error(f"Related instance not found: {related_model.__name__} with ID {value}")

                    return None
                except ValueError:
                    Logic.LOGGER.error(f"Invalid value for related instance: {value}")
                    return None

            else:
                return value
        except FieldDoesNotExist:
            Logic.LOGGER.error(f"Field not found: {field_name}")
            return None

    @staticmethod
    def update_json_field(instance, field, key, value):
        """Update the JSON field of the given instance

        Warning: this is experimental and attempts to update the data in nested JSON structures
        e.g. updating accountinfo data
        """
        json_data = getattr(instance, field, {}).copy()
        keys = key.split(':')
        data = json_data
        for k in keys[:-1]:
            data = data.setdefault(k, {})
        data[keys[-1]] = value
        setattr(instance, field, json_data)
