import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import ProgrammingError
from djpwr.managers import get_manager

from . import files

default_app_config = "djpwr.app_settings.apps.AppConfig"

logger = logging.getLogger(__name__)


class AppSettingDict:
    def __getitem__(self, setting_label):
        app_label, model_name, setting_name = setting_label.split(".")
        group_name = ".".join([app_label, model_name])

        try:
            setting = get_manager("app_settings.ApplicationSetting").get(
                group__group_name=group_name,
                name=setting_name,
            )
        except ProgrammingError:
            logger.error(
                "Catching exception in AppSettingDict.__getitem__ for %s, "
                "please check if migrations for this app have been run.",
                setting_label,
            )
            return
        except ObjectDoesNotExist:
            raise KeyError(setting_label)

        return setting.value

    def __setitem__(self, setting_label, value):
        app_label, model_name, setting_name = setting_label.split(".")
        group_name = ".".join([app_label, model_name])

        setting = get_manager("app_settings.ApplicationSetting").get(
            group__group_name=group_name,
            name=setting_name,
        )

        get_manager("app_settings.SettingGroup").touch_last_modified(setting.group)

        if files.is_file_setting(group_name, setting_name):
            files.set_item(group_name, setting_name, setting, value)
            return

        setting.value = value
        setting.save()

    def get(self, setting_label, default=None):
        try:
            return self[setting_label]
        except KeyError:
            return default

    def __contains__(self, setting_label):
        try:
            self[setting_label]
        except KeyError:
            return False
        return True


app_settings = AppSettingDict()
APP_SETTINGS = app_settings
