"""
Django app configuration for core.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'id'
    name = 'core'
    verbose_name = 'Core'