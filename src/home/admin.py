from django.contrib import admin
from django.utils.translation import gettext as _

from django_admin_inline_paginator_plus.admin import TabularInlinePaginated

from core.admin import TimestampedAdmin
from core.admin_mixins import CustomFieldsRendererMixin

from .admin_filters import RegistrationStatusFilter
from .forms import SpecimenAdminForm
from .models import Box, OriginalTrainer, PersonalDex, Slot, Specimen


class SlotInline(TabularInlinePaginated, CustomFieldsRendererMixin):
    model = Slot
    can_delete = False
    extra = 0
    fields = (
        "render_sprite",
        "position",
        "row",
        "col",
        "specimen",
    )
    per_page = 30
    raw_id_fields = ("specimen",)
    readonly_fields = ("render_sprite", "position", "row", "col")
    show_change_link = True

    class Media:
        css = {"all": ("css/styles.css",)}

    def render_sprite(self, obj):
        is_registred = obj.specimen is not None
        opt = "front_default"

        if obj.personal_dex and obj.personal_dex.is_shiny_dex:
            if is_registred and obj.specimen.is_shiny:
                opt = "front_shiny"

        return super().render_sprite(obj, opt, is_registred)

    render_sprite.short_description = _("sprite")


@admin.register(Box)
class BoxAdmin(TimestampedAdmin):
    list_display = ("name", "position")
    search_fields = ("name",)
    ordering = ("position",)
    inlines = (SlotInline,)


@admin.register(OriginalTrainer)
class OriginalTrainerAdmin(admin.ModelAdmin):
    list_display = ("__str__",)
    list_filter = ("version__name",)
    search_fields = ("trainer_id", "version__name", "name")


@admin.register(PersonalDex)
class PersonalDexAdmin(admin.ModelAdmin):
    inlines = (SlotInline,)
    filter_horizontal = ("forms",)
    list_display = (
        "name",
        "is_shiny_dex",
        "forms_count",
        "slots_count",
    )
    list_filter = ("is_shiny_dex",)
    search_fields = ("name",)

    def forms_count(self, obj):
        return obj.forms.count()

    def slots_count(self, obj):
        return obj.slot_set.count()

    forms_count.short_description = _("forms")
    slots_count.short_description = _("slots")


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
    list_display = (
        "render_sprite",
        "form",
        "specimen",
        "personal_dex",
        "box",
        "row",
        "col",
        "position",
    )
    list_filter = (
        "personal_dex",
        RegistrationStatusFilter,
        "specimen__gender",
    )
    list_per_page = 30
    search_fields = (
        "box__name",
        "row",
        "col",
        "form__name",
    )
    show_facets = admin.ShowFacets.ALWAYS

    class Media:
        css = {"all": ("css/styles.css",)}
        js = ("js/admin_fk_pass.js",)

    def registration_status(self, obj):
        return obj.specimen is not None

    def render_sprite(self, obj):
        is_registred = obj.specimen is not None
        opt = "front_default"

        if obj.personal_dex and obj.personal_dex.is_shiny_dex:
            if is_registred and obj.specimen.is_shiny:
                opt = "front_shiny"

        return super().render_sprite(obj, opt, is_registred)


@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
    form = SpecimenAdminForm
    inlines = (SlotInline,)
    list_display = (
        "render_sprite",
        "render_label",
        "ability",
        "language",
        "render_gender",
        "nature",
        "is_alpha",
        "is_shiny",
        "ot",
        "captured_at",
    )
    list_filter = ("language", "gender", "is_alpha", "is_shiny", "ot")
    search_fields = (
        "form__name",
        "nickname",
        "ability",
        "nature",
        "ot__trainer_id",
        "captured_at",
    )
    show_facets = admin.ShowFacets.ALWAYS

    class Media:
        js = ("js/admin_load_abilities.js",)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)

        if "form_id" in request.GET:
            initial["form"] = request.GET["form_id"]

        return initial

    def render_label(self, obj):
        return obj.nickname if obj.nickname else obj.form.name

    def render_gender(self, obj):
        if obj.gender == "male":
            return "♂️"
        elif obj.gender == "female":
            return "♀️"

        return "-"

    def render_sprite(self, obj):
        opt = "front_shiny" if obj.is_shiny else "front_default"
        return super().render_sprite(obj.form, opt, True)

    render_label.short_description = _("nickname or form")
    render_gender.short_description = _("gender")
    render_sprite.short_description = _("sprite")
