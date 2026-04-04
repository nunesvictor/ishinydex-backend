from django.contrib import admin

from .models import Box, BoxSlot


class BoxSlotInline(admin.TabularInline):
    model = BoxSlot
    extra = 30
    can_delete = False
    readonly_fields = ("row", "col")

    class Media:
        css = {"all": ("css/admin_grid.css",)}


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = ("name", "position")
    search_fields = ("name",)
    ordering = ("position",)
    inlines = [BoxSlotInline]
