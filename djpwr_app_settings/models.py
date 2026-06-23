from django.apps import apps
from django.db import models
from django.db.models import base
from django.utils.translation import gettext_lazy as _
from picklefield import PickledObjectField

from djpwr.managers import get_model
from . import managers

MODEL_LABELS = []


class SettingGroupBase(base.ModelBase):
    def __new__(mcs, name, bases, attrs, **kwargs):
        model_class = super().__new__(mcs, name, bases, attrs, **kwargs)

        model_label = model_class.name_from_class()

        if model_label != 'app_settings.settinggroup':
            MODEL_LABELS.append(model_label)

        return model_class


class SettingGroup(models.Model, metaclass=SettingGroupBase):
    group_name = models.CharField(_("Name"), max_length=128, unique=True)
    # name = models.CharField(_("Name"), max_length=128, unique=True)
    # prefix = models.CharField(_("Prefix"), max_length=128, null=True, blank=True)
    last_modified = models.DateTimeField(_("Last modified"), auto_now=True)

    _internal_fields = ['id', 'group_name', 'last_modified', 'settinggroup_ptr_id']

    objects = managers.SettingGroupManager()

    class Meta:
        verbose_name = _("Setting group")
        verbose_name_plural = _("Setting groups")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def name_from_class(cls):
        return '{}.{}'.format(cls._meta.app_label, cls._meta.model_name)

    def __str__(self):

        model = get_model(self.group_name)

        return _("{model_name} for {app_label}").format(
            app_label=apps.get_app_config(model._meta.app_label).verbose_name,
            model_name=model._meta.verbose_name_plural,
        )


class ApplicationSetting(models.Model):
    group = models.ForeignKey(
        'app_settings.SettingGroup', verbose_name=_("Application settings"),
        related_name='application_settings', on_delete=models.CASCADE
    )

    name = models.CharField(_("Name"), max_length=128)
    value = PickledObjectField(_("Value"), null=True, blank=True)

    objects = managers.ApplicationSettingManager()

    class Meta:
        unique_together = [
            ['name', 'group'],
        ]

        verbose_name = _("Application setting")
        verbose_name_plural = _("Application settings")

    @property
    def group_name(self):
        return self.group.group_name


class SettingGroupMeta:
    managed = False
    default_related_name = '+'  # disable reverse accessor, avoids cross-app clashes
    verbose_name = _("Settings")
    verbose_name_plural = _("Settings")
