from typing import TYPE_CHECKING, Any

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedModel

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import (
        ManyRelatedManager,
        RelatedManager,
    )

# Ordem canônica das formas: nº da dex nacional (o pk da espécie) e, dentro da
# espécie, ``form_order``; o ``pk`` só desempata. O ``order`` da PokéAPI não
# serve: agrupa famílias até a 6ª geração e é quase arbitrário na 9ª.
FORM_NATIONAL_ORDERING = ("pokemon__species__id", "form_order", "pk")


class Move(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
    accuracy = models.PositiveIntegerField(_("accuracy"), blank=True, null=True)
    effect_chance = models.PositiveIntegerField(
        _("effect chance"), blank=True, null=True
    )
    pp = models.PositiveIntegerField(_("pp"))
    priority = models.IntegerField(_("priority"))
    power = models.PositiveIntegerField(_("power"), blank=True, null=True)
    damage_class = models.CharField(_("damage class"), max_length=255)
    generation = models.CharField(_("game generation"), max_length=255)
    target = models.CharField(_("target"), max_length=255)
    type = models.CharField(_("type"), max_length=255)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("move")
        verbose_name_plural = _("moves")

    def __str__(self):
        return self.name


class Name(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
    language = models.CharField(_("language"), max_length=255, default="en")

    class Meta(TimestampedModel.Meta):
        verbose_name = _("name")
        verbose_name_plural = _("names")

    def __str__(self):
        return self.name


class PokemonAbility(TimestampedModel):
    slot = models.PositiveIntegerField(_("slot"))
    is_hidden = models.BooleanField(_("is hidden"), default=False)
    ability = models.CharField(_("ability"), max_length=255)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon ability")
        verbose_name_plural = _("pokémon abilities")
        unique_together = ("slot", "ability", "is_hidden")

    def __str__(self):
        return self.ability


class PokemonFormType(TimestampedModel):
    slot = models.PositiveIntegerField(_("slot"))
    type = models.CharField(_("type"), max_length=255)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon form type")
        verbose_name_plural = _("pokémon form types")
        ordering = ("slot",)

    def __str__(self):
        return f"{self.type}"


class PokemonForm(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    pokeapi_id = models.PositiveIntegerField(_("PokéAPI ID"))
    order = models.PositiveIntegerField(_("order"))
    form_order = models.PositiveIntegerField(_("form order"))
    is_default = models.BooleanField(_("is default"), default=True)
    is_battle_only = models.BooleanField(_("is battle only"), default=False)
    is_mega = models.BooleanField(_("is mega"), default=False)
    form_name = models.CharField(_("form name"), max_length=255)
    types = models.ManyToManyField(PokemonFormType, related_name="pokemon_forms")
    sprites = models.JSONField(_("sprites"), default=dict)
    version_group = models.ForeignKey(
        "VersionGroup", on_delete=models.CASCADE, related_name="pokemon_forms"
    )
    names = models.ManyToManyField("Name", related_name="pokemon_forms_names")
    form_names = models.ManyToManyField("Name", related_name="pokemon_forms_form_names")
    pokemon = models.ForeignKey(
        "Pokemon", on_delete=models.CASCADE, related_name="forms", blank=True, null=True
    )

    # Relação reversa criada pelo Django em runtime: anotada para o pyright.
    shinylocks: "ManyRelatedManager[ShinyLock, Any]"

    @property
    def is_distro_only(self):
        return self.shinylocks.filter(
            active=True, lock_type=ShinyLock.LockTypeChoices.DISTRO_ONLY
        ).exists()

    @property
    def is_shinylocked(self):
        return self.shinylocks.filter(
            active=True, lock_type=ShinyLock.LockTypeChoices.UNOBTAINABLE
        ).exists()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon form")
        verbose_name_plural = _("pokémon forms")
        ordering = FORM_NATIONAL_ORDERING

    def __str__(self):
        # Sem pk não há como consultar M2M; consultar geraria um erro cuja
        # mensagem chama __str__ de novo (RecursionError).
        if self.pk is None:
            return self.name

        match self.shinylocks.filter(active=True).first():
            case ShinyLock(lock_type=ShinyLock.LockTypeChoices.DISTRO_ONLY):
                suffix = "🎁"
            case ShinyLock(lock_type=ShinyLock.LockTypeChoices.UNOBTAINABLE):
                suffix = "🔒"
            case _:
                suffix = ""

        return f"{self.name}{suffix}"


class PokemonMove(TimestampedModel):
    move = models.ForeignKey(Move, on_delete=models.CASCADE)
    version_group_details = models.ManyToManyField(
        "PokemonMoveVersion", related_name="moves"
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon move")
        verbose_name_plural = _("pokémon moves")

    def __str__(self):
        return self.move.name


class PokemonMoveVersion(TimestampedModel):
    move_learn_method = models.CharField(_("move learn method"), max_length=255)
    version_group = models.ForeignKey("VersionGroup", on_delete=models.CASCADE)
    level_learned_at = models.PositiveIntegerField(_("level learned at"))
    order = models.PositiveIntegerField(_("order"), blank=True, null=True)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon move version")
        verbose_name_plural = _("pokémon move versions")


class PokemonSpecies(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    order = models.PositiveIntegerField(_("order"))
    gender_rate = models.IntegerField(_("gender rate"))
    capture_rate = models.PositiveIntegerField(_("capture rate"))
    base_happiness = models.PositiveIntegerField(_("base happiness"))
    is_baby = models.BooleanField(_("is baby"), default=False)
    is_legendary = models.BooleanField(_("is legendary"), default=False)
    is_mythical = models.BooleanField(_("is mythical"), default=False)
    hatch_counter = models.PositiveIntegerField(_("hatch counter"))
    has_gender_differences = models.BooleanField(
        _("has gender differences"), default=False
    )
    forms_switchable = models.BooleanField(_("forms switchable"), default=False)
    growth_rate = models.CharField(_("growth rate"), max_length=255)
    pokedex_numbers = models.ManyToManyField(
        "PokemonSpeciesDexEntry", related_name="pokemon_species"
    )
    egg_groups = models.JSONField(_("egg groups"), default=list)
    color = models.CharField(_("color"), max_length=255)
    shape = models.CharField(_("shape"), max_length=255)
    evolves_from_species = models.ForeignKey(
        "self",
        related_name="evolves_to_species",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    generation = models.CharField(_("game generation"), max_length=255)
    names = models.ManyToManyField(Name, related_name="pokemon_species_names")
    varieties = models.ManyToManyField(
        "PokemonSpeciesVariety", related_name="pokemon_species_varieties"
    )

    pokemons: "RelatedManager[Pokemon]"

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon species")
        verbose_name_plural = _("pokémon species")

    def __str__(self):
        return self.name


class PokemonSpeciesVariety(TimestampedModel):
    is_default = models.BooleanField(_("is default"), default=True)
    pokemon = models.ForeignKey(
        "Pokemon", on_delete=models.CASCADE, related_name="pokemon_species_varieties"
    )
    pokemon_id: int

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon species variety")
        verbose_name_plural = _("pokémon species varieties")

    def __str__(self):
        return (
            f"{self.pokemon.name} (default)" if self.is_default else self.pokemon.name
        )


class PokemonSpeciesDexEntry(TimestampedModel):
    entry_number = models.PositiveIntegerField(_("entry number"))
    pokedex = models.CharField(_("pokédex"), max_length=255)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon species dex entry")
        verbose_name_plural = _("pokémon species dex entries")

    def __str__(self):
        return f"{self.pokedex}#{self.entry_number}"


class PokemonStat(TimestampedModel):
    stat = models.CharField(_("stat"), max_length=255)
    effort = models.PositiveIntegerField(_("effort"))
    base_stat = models.PositiveIntegerField(_("base stat"))

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon stat")
        verbose_name_plural = _("pokémon stats")

    def __str__(self):
        return f"{self.stat}: {self.base_stat}"


class PokemonType(TimestampedModel):
    slot = models.PositiveIntegerField(_("slot"))
    type = models.CharField(_("type"), max_length=255)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon type")
        verbose_name_plural = _("pokémon types")
        ordering = ("slot",)

    def __str__(self):
        return f"{self.type}"


class Pokemon(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    pokeapi_id = models.PositiveIntegerField(_("PokéAPI ID"), default=1)
    base_experience = models.PositiveIntegerField(
        _("base experience"), blank=True, null=True
    )
    height = models.PositiveIntegerField(_("height"))
    is_default = models.BooleanField(_("is default"), default=True)
    order = models.IntegerField(_("order"))
    weight = models.PositiveIntegerField(_("weight"))
    abilities = models.ManyToManyField(PokemonAbility, related_name="pokemons")
    game_indices = models.ManyToManyField("VersionGameIndex", related_name="pokemons")
    moves = models.ManyToManyField(PokemonMove, related_name="pokemons")
    sprites = models.JSONField(_("sprites"), default=dict)
    cries = models.JSONField(_("cries"), default=dict)
    species = models.ForeignKey(
        PokemonSpecies,
        on_delete=models.CASCADE,
        related_name="pokemons",
        blank=True,
        null=True,
    )
    stats = models.ManyToManyField(PokemonStat, related_name="pokemons")
    types = models.ManyToManyField(PokemonType, related_name="pokemons")

    forms: "RelatedManager[PokemonForm]"

    class Meta(TimestampedModel.Meta):
        verbose_name = _("pokémon")
        verbose_name_plural = _("pokémons")
        ordering = ("order",)

    def __str__(self):
        return self.name


class ShinyLock(TimestampedModel):
    class LockTypeChoices(models.TextChoices):
        DISTRO_ONLY = "distro-only", _("distro only")
        UNOBTAINABLE = "unobtainable", _("unobtainable")

    caption = models.CharField(_("caption"), max_length=50, unique=True)
    description = models.TextField(_("description"), blank=True, null=True)
    lock_type = models.CharField(
        _("lock type"),
        choices=LockTypeChoices.choices,
        default=LockTypeChoices.UNOBTAINABLE,
    )
    forms = models.ManyToManyField(PokemonForm, related_name="shinylocks")
    active = models.BooleanField(_("active"), default=True)

    def __str__(self):
        return self.caption


class Version(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    version_group = models.ForeignKey("VersionGroup", on_delete=models.CASCADE)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("version")
        verbose_name_plural = _("versions")
        ordering = ("version_group__order",)

    def __str__(self):
        return self.name


class VersionGameIndex(TimestampedModel):
    game_index = models.PositiveIntegerField(_("game index"))
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("version game index")
        verbose_name_plural = _("version game indexes")

    def __str__(self):
        return f"{self.version}#{self.game_index}"


class VersionGroup(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    generation = models.CharField(_("game generation"), max_length=255)
    order = models.PositiveIntegerField(_("order"))
    pokedexes = models.JSONField(_("pokédexes"), default=list)
    regions = models.JSONField(_("regions"), default=list)
    versions = models.JSONField(_("versions"), default=list)

    class Meta(TimestampedModel.Meta):
        verbose_name = _("version group")
        verbose_name_plural = _("version groups")
        ordering = ("order",)

    def __str__(self):
        return self.name
