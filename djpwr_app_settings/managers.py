from django.db.models import NOT_PROVIDED
from django.utils import timezone

from djpwr.managers import get_manager, get_model, QuerySet, from_queryset


class SettingGroupQuerySet(QuerySet):
    pass


class SettingGroupManager(from_queryset(SettingGroupQuerySet)):
    def create_group(self, group_name):
        setting_group, _ = self.get_or_create(group_name=group_name)

        return setting_group

    def touch_last_modified(self, setting):
        now = timezone.now()

        self.filter(
            id=setting.id,
            last_modified__lte=now
        ).update(last_modified=now)


class ApplicationSettingQuerySet(QuerySet):
    pass


class ApplicationSettingManager(from_queryset(ApplicationSettingQuerySet)):
    queryset_class = ApplicationSettingQuerySet

    def create_for_group(self, setting_group):
        setting_model = get_model(setting_group.group_name)

        for field in setting_model._meta.fields:
            if field.attname in setting_model._internal_fields:
                continue

            if field.default == NOT_PROVIDED:
                value = None
            else:
                value = field.default

            self.get_or_create(
                group=setting_group,
                name=field.attname,
                defaults={'value': value}
            )
