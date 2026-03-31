"""File-related handling for FileField-based app settings."""

from django.core.files.uploadedfile import UploadedFile
from django.db.models import FileField
from djpwr.managers import get_model


def set_item(group_name: str, setting_name: str, setting, new_value) -> None:
    """Save or clear a file setting, respecting the field's storage and upload_to."""
    field = _setting_model_field(group_name, setting_name)
    old_storage_value = setting.value or ""

    if not new_value:
        _delete_file(field, old_storage_value)
        setting.value = new_value
    elif not isinstance(new_value, UploadedFile):
        # FieldFile or string path — already stored, nothing to do
        return
    else:
        _delete_file(field, old_storage_value)
        model = get_model(group_name)
        upload_path = field.generate_filename(model(), new_value.name)
        saved_name = field.storage.save(upload_path, new_value)
        setting.value = saved_name

    setting.save()


def is_file_setting(group_name: str, setting_name: str) -> bool:
    """Return True if the setting corresponds to a FileField."""
    field = _setting_model_field(group_name, setting_name)
    return isinstance(field, FileField)


def _setting_model_field(group_name: str, setting_name: str):
    """Return the model field for a setting, or None if not found."""
    try:
        model = get_model(group_name)
        return model._meta.get_field(setting_name)
    except Exception:
        return None


def _delete_file(field: FileField, name: str) -> None:
    """Delete a file from storage, silently ignoring errors."""
    if not name:
        return
    try:
        field.storage.delete(name)
    except Exception:
        pass
