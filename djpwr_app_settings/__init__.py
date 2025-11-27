import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import ProgrammingError
from djpwr.managers import get_manager

default_app_config = 'djpwr.app_settings.apps.AppConfig'


logger = logging.getLogger(__name__)


class AppSettingDict:
    def __getitem__(self, setting_label):
        app_label, model_name, setting_name = setting_label.split('.')

        try:
            setting = get_manager('app_settings.ApplicationSetting').get(
                group__group_name='.'.join([app_label, model_name]),
                name=setting_name
            )
        except ProgrammingError:
            # This exception occurs when the migrations of this app have not been
            # run yet, as can happen when this app is newly added and this
            # implementation is called from the code at Python runtime.
            logger.error(
                f"Catching exception in AppSettingDict.__getitem__ for {setting_label}, "
                f" please check if migrations for this app have been run."
            )
            return
        except ObjectDoesNotExist:
            raise KeyError(setting_label)

        return setting.value

    def __setitem__(self, setting_label, value):
        app_label, model_name, setting_name = setting_label.split('.')

        setting = get_manager('app_settings.ApplicationSetting').get(
            group__group_name='.'.join([app_label, model_name]),
            name=setting_name
        )
        setting.value = value
        setting.save()

        get_manager('app_settings.SettingGroup').touch_last_modified(setting.group)

    def get(self, setting_label, default=None):
        """
        Dict-like get(): returns default when key is missing
        """
        try:
            return self[setting_label]
        except KeyError:
            return default

    def __contains__(self, setting_label):
        """
        Provide `in` checks: 'appname.interal.somekey' in app_settings
        """
        try:
            self[setting_label]
        except KeyError:
            return False
        return True


app_settings = AppSettingDict()

APP_SETTINGS = app_settings
