from django.apps import AppConfig as BaseAppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


class AppConfig(BaseAppConfig):
    name = 'djpwr_app_settings'
    label = 'app_settings'
    verbose_name = _("Application settings")

    def ready(self):
        from .signals import setup_app_settings
        post_migrate.connect(setup_app_settings, sender=self)
