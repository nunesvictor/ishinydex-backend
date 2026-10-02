from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from core.admin_mixins import CustomFieldsRendererMixin

from .admin_filters import EggGroupFilter
from .forms import PokemonSpeciesAdminForm
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

    def has_add_permission(self, request, obj=None):
        # Formas vêm da PokéAPI, assim como em PokemonFormAdmin.
        return False


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
    show_facets = admin.ShowFacets.ALWAYS

    def has_add_permission(self, request):
        return False


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
        "species__id",
        "-is_default",
        "pk",
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

    def has_add_permission(self, request):
        return False


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
    ordering = FORM_NATIONAL_ORDERING
    search_fields = (
        "name",
        "types__type",
        "pokemon__species__generation",
    )
    show_facets = admin.ShowFacets.ALWAYS

    def has_add_permission(self, request):
        return False


@admin.register(PokemonSpecies)
class PokemonSpeciesAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
    filter_horizontal = (
        "pokedex_numbers",
        "names",
        "varieties",
    )
    form = PokemonSpeciesAdminForm
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
    ordering = ("pk",)
    search_fields = (
        "name",
        "names__name",
        "generation",
        "egg_groups",
        "color",
        "shape",
    )
    show_facets = admin.ShowFacets.ALWAYS

    def has_add_permission(self, request):
        return False

    def _default_pokemon(self, obj: PokemonSpecies):
        variety = obj.varieties.filter(is_default=True).first()
        return variety.pokemon if variety else None

    @admin.display(description=_("national pokedex id"))
    def render_national_pokedex_id(self, obj: PokemonSpecies):
        entry = obj.pokedex_numbers.filter(pokedex="national").first()
        return entry.entry_number if entry else "-"

    def render_sprite(self, obj: PokemonSpecies):  # type: ignore[override]
        return super().render_sprite(obj=self._default_pokemon(obj))

    def render_types(self, obj: PokemonSpecies):  # type: ignore[override]
        pokemon = self._default_pokemon(obj)
        return super().render_types(pokemon) if pokemon else "-"


@admin.register(ShinyLock)
class ShinyLockAdmin(admin.ModelAdmin):
    filter_horizontal = ("forms",)
    list_display = (
        "caption",
        "description",
        "lock_type",
        "active",
    )
    list_filter = (
        "lock_type",
        "active",
    )
    search_fields = (
        "caption",
        "description",
        "forms__name",
    )


@admin.register(Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "version_group",
    )

    def has_add_permission(self, request):
        return False


@admin.register(VersionGroup)
class VersionGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "generation",
        "order",
    )
    list_filter = ("generation",)

    def has_add_permission(self, request):
        return False
