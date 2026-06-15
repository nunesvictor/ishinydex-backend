from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext as _

from .admin_filters import EggGroupFilter
from .models import (
    Move,
    Pokemon,
    PokemonSpecies,
)


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Pokemon)
class PokemonAdmin(admin.ModelAdmin):
    filter_horizontal = (
        "abilities",
        "game_indices",
        "moves",
        "stats",
        "types",
    )
    list_display = ("render_sprite", "name", "order", "height", "weight")
    list_filter = (
        "is_default",
        "types__type",
        "species__generation",
        "game_indices__version",
    )
    list_per_page = 6
    ordering = ("order",)
    search_fields = (
        "name",
        "abilities__ability",
        "moves__move__name",
    )

    def render_sprite(self, obj):
        return format_html(
            "<img src={} alt='{}' />", obj.sprites["front_default"], obj.name
        )

    render_sprite.short_description = "Sprite"


@admin.register(PokemonSpecies)
class PokemonSpeciesAdmin(admin.ModelAdmin):
    filter_horizontal = (
        "pokedex_numbers",
        "names",
        "varieties",
    )
    list_display = (
        "render_sprite",
        "name",
        "render_types",
        "render_national_pokedex_id",
        "order",
    )
    list_filter = (
        "varieties__pokemon__types__type",
        "is_baby",
        "is_legendary",
        "is_mythical",
        "forms_switchable",
        "generation",
        EggGroupFilter,
        "shape",
    )
    list_per_page = 6
    ordering = ("order",)
    search_fields = (
        "name",
        "names__name",
        "generation",
        "egg_groups",
        "color",
        "shape",
    )

    def render_national_pokedex_id(self, obj: PokemonSpecies):
        return obj.pokedex_numbers.filter(pokedex="national").first().entry_number

    def render_sprite(self, obj: PokemonSpecies):
        pokemon = obj.varieties.filter(is_default=True).first().pokemon

        return format_html(
            "<img src={} alt='{}' />", pokemon.sprites["front_default"], pokemon.name
        )

    def render_types(self, obj: PokemonSpecies):
        pokemon = obj.varieties.filter(is_default=True).first().pokemon

        return ", ".join([t.type for t in pokemon.types.all()])

    render_national_pokedex_id.short_description = _("national pokedex id")
    render_sprite.short_description = _("sprite")
    render_types.short_description = _("types")
