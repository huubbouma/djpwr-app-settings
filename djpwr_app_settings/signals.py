from django.db import transaction
from djpwr.managers import get_manager, get_model


def setup_app_settings(sender, **kwargs):
    from .models import MODEL_LABELS

    with transaction.atomic():
        for model_label in MODEL_LABELS:
            model_class = get_model(model_label)

            group_name = model_class.name_from_class()

            setting_group = get_manager('app_settings.SettingGroup').create_group(group_name)
            get_manager('app_settings.ApplicationSetting').create_for_group(setting_group)
