from django.contrib import admin
from django.utils.translation import gettext as _

from core.admin_mixins import CustomFieldsRendererMixin

from .admin_filters import EggGroupFilter
from .models import (
    Move,
    Pokemon,
    PokemonForm,
    PokemonSpecies,
)


class PokemonFormInline(admin.TabularInline, CustomFieldsRendererMixin):
    model = PokemonForm
    extra = 0
    max_num = 255
    can_delete = False
    show_change_link = False
    exclude = (
        "form_name",
        "form_names",
        "names",
        "sprites",
        "types",
        "version_group",
    )
    readonly_fields = (
        "render_sprite",
        "name",
        "render_types",
        "is_default",
        "is_battle_only",
        "is_mega",
        "order",
    )


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "accuracy",
        "power",
        "damage_class",
        "pp",
        "target",
    )
    list_filter = (
        "type",
        "damage_class",
        "generation",
    )
    list_per_page = 25
    ordering = ("name",)
    search_fields = (
        "name",
        "damage_class",
        "target",
        "type",
        "pokemonmove__pokemons__name",
    )


@admin.register(Pokemon)
class PokemonAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
    inlines = (PokemonFormInline,)
    list_display = (
        "render_sprite",
        "name",
        "render_types",
        "height",
        "weight",
        "order",
    )
    list_filter = (
        "is_default",
        "forms__is_mega",
        "forms__is_battle_only",
        "types__type",
        "species__generation",
        "game_indices__version",
    )
    list_per_page = 6
    ordering = (
        "species__order",
        "order",
    )
    readonly_fields = (
        "abilities",
        "game_indices",
        "moves",
        "stats",
        "types",
    )
    search_fields = (
        "name",
        "abilities__ability",
        "moves__move__name",
    )
    show_facets = admin.ShowFacets.ALWAYS


@admin.register(PokemonForm)
class PokemonFormAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
    list_display = (
        "render_sprite",
        "name",
        "render_types",
        "is_default",
        "is_battle_only",
        "is_mega",
        "order",
    )
    list_filter = (
        "personaldex",
        "types__type",
        "pokemon__species__generation",
        "is_default",
        "is_battle_only",
        "is_mega",
    )
    list_per_page = 6
    ordering = (
        "pokemon__species__order",
        "order",
    )
    search_fields = (
        "name",
        "types__type",
        "pokemon__species__generation",
    )
    show_facets = admin.ShowFacets.ALWAYS


@admin.register(PokemonSpecies)
class PokemonSpeciesAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
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
    show_facets = admin.ShowFacets.ALWAYS

    def render_national_pokedex_id(self, obj: PokemonSpecies):
        return obj.pokedex_numbers.filter(pokedex="national").first().entry_number

    def render_sprite(self, obj: PokemonSpecies):
        pokemon = obj.varieties.filter(is_default=True).first().pokemon
        return super().render_sprite(pokemon)

    def render_types(self, obj: PokemonSpecies):
        pokemon = obj.varieties.filter(is_default=True).first().pokemon
        return super().render_types(pokemon)

    render_national_pokedex_id.short_description = _("national pokedex id")
