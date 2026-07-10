from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from django_admin_inline_paginator_plus.admin import TabularInlinePaginated

from core.admin import TimestampedAdmin
from core.admin_mixins import CustomFieldsRendererMixin

from .admin_filters import RegistrationStatusFilter
from .forms import SpecimenAdminForm
from .models import DEFAULT_POKEMON_BOX_SIZE as BOX_SIZE
from .models import (
    Box,
    OriginalTrainer,
    PersonalDex,
    Slot,
    Specimen,
)
from .utils import list_humanize


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
    list_display = (
        "name",
        "position",
        "is_schema_configured",
        "is_schema_filled_out",
        "empty_slots",
    )
    search_fields = ("name",)
    ordering = ("position",)
    inlines = (SlotInline,)

    @admin.display(boolean=True, description=_("is schema configured"))
    def is_schema_configured(self, obj):
        return any([s.personal_dex for s in obj.slots.all()])

    @admin.display(boolean=True, description=_("is schema filled out"))
    def is_schema_filled_out(self, obj):
        if obj.slots.count() == 0:
            return False

        return not obj.slots.filter(form__isnull=False, specimen__isnull=True).exists()

    @admin.display(description=_("empty slots"))
    def empty_slots(self, obj):
        return list_humanize(
            [
                ((s.position - 1) % BOX_SIZE) + 1
                for s in obj.slots.filter(form__isnull=False, specimen__isnull=True)
            ],
        )


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
    exclude = ("position",)
    list_display = (
        "render_sprite",
        "form",
        "specimen",
        "personal_dex",
        "box",
        "row",
        "col",
        "relative_position",
    )
    list_filter = (
        "personal_dex",
        RegistrationStatusFilter,
        "row",
        "col",
        "box",
    )
    list_per_page = 30
    readonly_fields = (
        "row",
        "col",
    )
    search_fields = (
        "box__name",
        "row",
        "col",
        "form__name",
    )
    show_facets = admin.ShowFacets.ALWAYS

    class Media:
        css = {"all": ("css/styles.css",)}
        js = (
            "admin/js/vendor/jquery/jquery.js",
            "admin/js/admin/RelatedObjectLookups.js",
            "js/admin_fk_pass.js",
            "js/admin_fix_focus.js",
        )

    @admin.display(description=_("relative position"))
    def relative_position(self, obj):
        return (obj.position - 1) % BOX_SIZE + 1

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        context["show_save_as_new"] = False
        context["show_save_and_add_another"] = False
        context["show_save_and_move_on"] = True
        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_change(self, request, obj):
        response = super().response_change(request, obj)

        if "_moveon" in request.POST:
            next_obj = Slot.objects.filter(id__gt=obj.id).order_by("id").first()
            return HttpResponseRedirect(
                reverse("admin:home_slot_change", args=[next_obj.id])
            )

        return response

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
