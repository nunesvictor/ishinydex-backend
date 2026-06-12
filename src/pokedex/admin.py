from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Move,
    Pokemon,
    PokemonAbility,
    PokemonForm,
    PokemonFormType,
    PokemonSpecies,
    PokemonType,
    VersionGameIndex,
)


@admin.register(Pokemon)
class PokemonAdmin(admin.ModelAdmin):
    readonly_fields = (
        "abilities",
        "game_indices",
        "moves",
    )
    list_display = ("render_sprite", "name", "order", "height", "weight")
    list_filter = ("abilities",)
    list_per_page = 6
    ordering = ("order",)
    search_fields = (
        "name",
        "abilities__ability",
        "moves__move",
    )

    def render_sprite(self, obj):
        return format_html(
            "<img src={} alt='{}' />", obj.sprites["front_default"], obj.name
        )

    render_sprite.short_description = "Sprite"


@admin.register(PokemonAbility)
class PokemonAbilityAdmin(admin.ModelAdmin):
    list_display = ("ability", "slot", "is_hidden")
    list_filter = ("is_hidden",)
    search_fields = ("ability",)
    ordering = ("ability",)


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(VersionGameIndex)
class VersionGameIndexAdmin(admin.ModelAdmin):
    list_display = ("version", "game_index")
    list_filter = ("version",)
    search_fields = ("version",)


admin.site.register(PokemonForm)
admin.site.register(PokemonFormType)
admin.site.register(PokemonSpecies)
admin.site.register(PokemonType)
