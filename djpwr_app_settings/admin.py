from functools import update_wrapper

from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.auth.admin import csrf_protect_m
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.db.models.fields.files import FileField
from django.forms import all_valid

try:
    from django.utils.translation import gettext_lazy as _
except:
    from django.utils.translation import ugettext_lazy as _

from djpwr.managers import get_manager

from . import APP_SETTINGS, models


class ApplicationSettingAdmin(admin.ModelAdmin):
    list_display = ["group_name", "name"]


admin.site.register(models.ApplicationSetting, ApplicationSettingAdmin)


class SettingGroupAdmin(admin.ModelAdmin):
    readonly_fields = ["last_modified"]
    exclude = ["group_name"]

    def get_urls(self):
        from django.urls import path

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urlpatterns = [
            path("", wrap(self.change_view), name="%s_%s_change" % info),
            path("", wrap(self.change_view), name="%s_%s_changelist" % info),
        ]
        return urlpatterns

    def change_view(self, request, form_url="", extra_context=None):
        return self.changeform_view(request, form_url, extra_context)

    @csrf_protect_m
    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        with transaction.atomic(using=router.db_for_write(self.model)):
            return self._changeform_view(request, object_id, form_url, extra_context)

    def _changeform_view(self, request, object_id, form_url, extra_context):
        model = self.model
        opts = model._meta

        setting_group = get_manager("app_settings.SettingGroup").get(
            group_name=model.name_from_class()
        )

        obj = model(
            pk=setting_group.pk,
            group_name=setting_group.group_name,
            last_modified=setting_group.last_modified,
        )

        if request.method == "POST":
            if not self.has_change_permission(request, obj):
                raise PermissionDenied
        else:
            if not self.has_view_or_change_permission(request, obj):
                raise PermissionDenied

        add = False
        ModelForm = self.get_form(request, obj, change=not add)

        if request.method == "POST":
            # 1) hydrate obj from stored settings, so FileField has its old value
            initial_settings = self.get_changeform_initial_data(request)
            for field_name, value in initial_settings.items():
                if hasattr(obj, field_name):
                    setattr(obj, field_name, value)

            form = ModelForm(request.POST, request.FILES, instance=obj)
            form_validated = form.is_valid()
            if form_validated:
                new_object = self.save_form(request, form, change=not add)
            else:
                new_object = form.instance

            formsets, inline_instances = self._create_formsets(
                request, new_object, change=not add
            )
            if all_valid(formsets) and form_validated:
                self.save_model(request, new_object, form, not add)
                self.save_related(request, form, formsets, not add)
                change_message = self.construct_change_message(
                    request, form, formsets, add
                )
                if add:
                    self.log_addition(request, new_object, change_message)
                    return self.response_add(request, new_object)
                else:
                    self.log_change(request, new_object, change_message)
                    return self.response_change(request, new_object)
            else:
                form_validated = False
        else:
            # GET
            initial = self.get_changeform_initial_data(request)
            initial["last_modified"] = obj.last_modified

            # hydrate the instance as well (including FileField)
            for field_name, value in list(initial.items()):  # make a copy
                if hasattr(obj, field_name):
                    field = obj._meta.get_field(field_name)
                    setattr(obj, field_name, value)
                    if isinstance(field, FileField):
                        initial.pop(field_name, None)

            form = ModelForm(instance=obj, initial=initial)
            formsets, inline_instances = self._create_formsets(
                request, form.instance, change=not add
            )

        if not add and not self.has_change_permission(request, obj):
            readonly_fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        else:
            readonly_fields = self.get_readonly_fields(request, obj)
        adminForm = helpers.AdminForm(
            form,
            list(self.get_fieldsets(request, obj)),
            # Clear prepopulated fields on a view-only form to avoid a crash.
            (
                self.get_prepopulated_fields(request, obj)
                if add or self.has_change_permission(request, obj)
                else {}
            ),
            readonly_fields,
            model_admin=self,
        )
        media = self.media + adminForm.media

        inline_formsets = self.get_inline_formsets(
            request, formsets, inline_instances, obj
        )
        for inline_formset in inline_formsets:
            media = media + inline_formset.media

        if add:
            title = _("Add %s")
        elif self.has_change_permission(request, obj):
            title = _("Change %s")
        else:
            title = _("View %s")
        context = {
            **self.admin_site.each_context(request),
            "title": title % opts.verbose_name,
            "adminform": adminForm,
            "original": obj,
            "is_popup": IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
            "media": media,
            "inline_admin_formsets": inline_formsets,
            "errors": helpers.AdminErrorList(form, formsets),
            "preserved_filters": self.get_preserved_filters(request),
        }

        # Hide the "Save" and "Save and continue" buttons if "Save as New" was
        # previously chosen to prevent the interface from getting confusing.
        if (
            request.method == "POST"
            and not form_validated
            and "_saveasnew" in request.POST
        ):
            context["show_save"] = False
            context["show_save_and_continue"] = False
            # Use the change template instead of the add template.
            add = False

        context.update(extra_context or {})

        return self.render_change_form(
            request, context, add=add, change=not add, obj=obj, form_url=form_url
        )

    def get_changeform_initial_data(self, request):
        settings = (
            get_manager("app_settings.ApplicationSetting")
            .filter(group__group_name=self.model.name_from_class())
            .values_list("name", "value")
        )

        return dict(settings)

    def save_model(self, request, obj, form, change):
        group_name = obj.name_from_class()

        for field_name, value in form.cleaned_data.items():
            if field_name in obj._internal_fields:
                continue

            field = obj._meta.get_field(field_name)

            if isinstance(field, FileField):
                # Handle FileField semantics:
                # - value is False -> clear
                # - value is None / "" -> keep existing
                if value is False:
                    APP_SETTINGS[".".join([group_name, field_name])] = None
                    continue
                if not value:
                    # keep old value in APP_SETTINGS, do not overwrite
                    continue

            APP_SETTINGS[".".join([group_name, field_name])] = value

        return obj

    def has_add_permission(self, request):
        return False


admin.site.register(models.SettingGroup, SettingGroupAdmin)
