"""Admin padrão do Django, para acesso emergencial e debug.

Os dados do pokedex vêm da PokéAPI (``sync_pokeapi``): sem adicionar pelo
admin. ``ShinyLock`` é a exceção, cadastrado à mão.
"""

from django.contrib import admin

from .models import (
    FORM_NATIONAL_ORDERING,
    Move,
    Pokemon,
    PokemonForm,
    PokemonSpecies,
    ShinyLock,
    Version,
    VersionGroup,
)


class PokeAPIAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False


@admin.register(Move)
class MoveAdmin(PokeAPIAdmin):
    list_display = ("name", "type", "damage_class", "power", "accuracy", "pp")
    list_filter = ("type", "damage_class", "generation")
    ordering = ("name",)
    search_fields = ("name",)


@admin.register(Pokemon)
class PokemonAdmin(PokeAPIAdmin):
    list_display = ("name", "pokeapi_id", "is_default", "order")
    list_filter = ("is_default", "species__generation")
    ordering = ("species__id", "-is_default", "pk")
    raw_id_fields = ("species",)
    readonly_fields = ("abilities", "game_indices", "moves", "stats", "types")
    search_fields = ("name",)


@admin.register(PokemonForm)
class PokemonFormAdmin(PokeAPIAdmin):
    list_display = ("name", "pokeapi_id", "is_default", "is_battle_only", "is_mega")
    list_filter = ("is_default", "is_battle_only", "is_mega")
    ordering = FORM_NATIONAL_ORDERING
    raw_id_fields = ("pokemon",)
    readonly_fields = ("types", "names", "form_names")
    search_fields = ("name",)


@admin.register(PokemonSpecies)
class PokemonSpeciesAdmin(PokeAPIAdmin):
    list_display = ("name", "generation", "order")
    list_filter = ("generation", "is_baby", "is_legendary", "is_mythical")
    ordering = ("pk",)
    raw_id_fields = ("evolves_from_species",)
    readonly_fields = ("pokedex_numbers", "names", "varieties")
    search_fields = ("name",)


@admin.register(ShinyLock)
class ShinyLockAdmin(admin.ModelAdmin):
    filter_horizontal = ("forms",)
    list_display = ("caption", "lock_type", "active")
    list_filter = ("lock_type", "active")
    search_fields = ("caption", "description", "forms__name")


@admin.register(Version)
class VersionAdmin(PokeAPIAdmin):
    list_display = ("name", "version_group")


@admin.register(VersionGroup)
class VersionGroupAdmin(PokeAPIAdmin):
    list_display = ("name", "generation", "order")
    list_filter = ("generation",)
