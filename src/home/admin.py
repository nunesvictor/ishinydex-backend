from django.contrib import admin
from django.utils.translation import gettext as _

from django_admin_inline_paginator_plus.admin import TabularInlinePaginated

from core.admin_mixins import CustomFieldsRendererMixin

from .models import Box, PersonalDex, PokemonSpecimen, Slot


class SlotInline(TabularInlinePaginated, CustomFieldsRendererMixin):
    model = Slot
    can_delete = False
    extra = 0
    fields = ("render_sprite", "position", "row", "col", "specimen")
    per_page = 30
    raw_id_fields = ("specimen",)
    readonly_fields = ("render_sprite", "position", "row", "col")
    show_change_link = False

    def render_sprite(self, obj):
        opt = "front_default"

        if obj.personal_dex and obj.personal_dex.is_shiny_dex:
            opt = "front_shiny"

        return super().render_sprite(obj, opt)


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = ("name", "position")
    search_fields = ("name",)
    ordering = ("position",)
    inlines = (SlotInline,)


@admin.register(PokemonSpecimen)
class PokemonSpecimenAdmin(admin.ModelAdmin):
    list_display = ("__str__", "nickname", "form", "is_shiny", "is_legendary")
    search_fields = ("nickname", "ndex_id")
    list_filter = ("is_shiny", "is_legendary", "is_mythical", "is_mega", "is_gmax")
    ordering = ("ndex_id",)


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
        "box",
        "row",
        "col",
        "personal_dex",
        "form",
        "specimen",
    )
    list_per_page = 30

    def render_sprite(self, obj):
        opt = "front_default"

        if obj.personal_dex and obj.personal_dex.is_shiny_dex:
            opt = "front_shiny"

        return super().render_sprite(obj, opt)
