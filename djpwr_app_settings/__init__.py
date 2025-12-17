import logging
import os

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db import ProgrammingError
from django.db.models import FileField
from django.db.models.fields.files import FieldFile
from djpwr.managers import get_manager, get_model

default_app_config = "djpwr.app_settings.apps.AppConfig"

logger = logging.getLogger(__name__)


def _setting_model_field(group_name: str, setting_name: str):
    try:
        model = get_model(group_name)
        return model._meta.get_field(setting_name)
    except Exception:
        return None


def _is_file_setting(group_name: str, setting_name: str) -> bool:
    field = _setting_model_field(group_name, setting_name)
    return isinstance(field, FileField)


def _storage_path_for(
    app_label: str, model_name: str, setting_name: str, filename: str
) -> str:
    filename = os.path.basename(filename) or "upload"
    return f"app_settings/{app_label}/{model_name}/{setting_name}/{filename}"


def _delete_storage_name(name: str) -> None:
    if not name:
        return
    try:
        default_storage.delete(name)
    except Exception:
        # Never block saving settings on storage delete issues
        pass


def _extract_storage_value(value) -> str:
    if isinstance(value, (FieldFile, File)):
        return getattr(value, "name", "") or ""
    return value


def _open_as_django_file(storage_name: str) -> File | None:
    """
    Open a stored file path and wrap it as django.core.files.base.File.
    Caller is responsible for closing it if needed (f.close()).
    """
    if not storage_name:
        return None
    try:
        f = default_storage.open(storage_name, "rb")
        return File(f, name=storage_name)
    except Exception:
        return None


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

        value = setting.value

        # If this is a FileField-setting, enforce: stored value == storage path string.
        if _is_file_setting(group_name, setting_name):
            storage_value = _extract_storage_value(value)
            return _open_as_django_file(storage_value)

        return value

    def __setitem__(self, setting_label, value):
        app_label, model_name, setting_name = setting_label.split(".")
        group_name = ".".join([app_label, model_name])

        setting = get_manager("app_settings.ApplicationSetting").get(
            group__group_name=group_name,
            name=setting_name,
        )

        get_manager("app_settings.SettingGroup").touch_last_modified(setting.group)

        old_storage_value = _extract_storage_value(setting.value)

        # new file upload
        if isinstance(value, File) and not isinstance(value, FieldFile):
            _delete_storage_name(old_storage_value)

            storage_path = _storage_path_for(
                app_label, model_name, setting_name, value.name
            )
            saved_name = default_storage.save(storage_path, value)

            setting.value = saved_name
            setting.save()
            return

        # user cleared the value. If file, delete the old stored file.
        if not value:
            if _is_file_setting(group_name, setting_name):
                _delete_storage_name(old_storage_value)

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
