import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import ProgrammingError
from django.core.files.storage import default_storage
from django.core.files.base import File
from django.db.models.fields.files import FieldFile

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

        # Keep track of the old stored file (if any)
        old_value = setting.value
        old_name = ""
        if isinstance(old_value, (File, FieldFile)):
            old_name = old_value.name or ""

        # Case 1: user cleared the field (None / "" / False)
        if not value:
            if old_name:
                try:
                    # old_name may be a bare filename or a full path
                    if "/" in old_name:
                        storage_path = old_name
                    else:
                        storage_path = (
                            f"app_settings/{app_label}/{model_name}/{setting_name}/{old_name}"
                        )
                    default_storage.delete(storage_path)
                except Exception:
                    # Do not break settings saving if delete fails
                    pass

            setting.value = value

        else:
            # Case 2: new upload (InMemoryUploadedFile / TemporaryUploadedFile etc.)
            # File-like, but not FieldFile (which would be an existing stored file)
            if isinstance(value, File) and not isinstance(value, FieldFile):
                # Remove old file if there was one
                if old_name:
                    try:
                        if "/" in old_name:
                            old_storage_path = old_name
                        else:
                            old_storage_path = (
                                f"app_settings/{app_label}/{model_name}/{setting_name}/{old_name}"
                            )
                        default_storage.delete(old_storage_path)
                    except Exception:
                        # Ignore delete errors; saving the new file is more important
                        pass

                # Save the new file
                filename = (value.name or "").rsplit("/", 1)[-1]
                storage_path = (
                    f"app_settings/{app_label}/{model_name}/{setting_name}/{filename}"
                )
                saved_path = default_storage.save(storage_path, value)
                # Point the object to the stored path so .open() will work later
                value.name = saved_path
                setting.value = value

            else:
                # Case 3: non-file or existing FieldFile \u2192 just store as-is
                # (PickledObjectField will handle pickling)
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
        Provide `in` checks: 'appname.internal.somekey' in app_settings
        """
        try:
            self[setting_label]
        except KeyError:
            return False
        return True


app_settings = AppSettingDict()

APP_SETTINGS = app_settings
