from django.contrib import admin
from django.utils.translation import gettext as _

from .models import Box, PersonalDex, PokemonSpecimen, Slot


class SlotInline(admin.TabularInline):
    model = Slot
    extra = 0
    max_num = 30
    can_delete = False
    show_change_link = True
    fields = ("position", "row", "col", "specimen")
    readonly_fields = ("position", "row", "col")
    raw_id_fields = ("specimen",)


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = ("name", "position")
    search_fields = ("name",)
    ordering = ("position",)
    inlines = [SlotInline]


@admin.register(PokemonSpecimen)
class PokemonSpecimenAdmin(admin.ModelAdmin):
    list_display = ("__str__", "nickname", "form", "is_shiny", "is_legendary")
    search_fields = ("nickname", "ndex_id")
    list_filter = ("is_shiny", "is_legendary", "is_mythical", "is_mega", "is_gmax")
    ordering = ("ndex_id",)


@admin.register(PersonalDex)
class PersonalDexAdmin(admin.ModelAdmin):
    filter_horizontal = ("boxes", "forms")
    search_fields = ("name",)
    list_display = ("name", "forms_count")

    def boxes_count(self, obj):
        return obj.boxes.count()

    def forms_count(self, obj):
        return obj.forms.count()

    boxes_count.short_description = _("boxes")
    forms_count.short_description = _("forms")
