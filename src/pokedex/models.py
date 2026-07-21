from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimestampedModel


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

    def __str__(self):
        return self.name


class Name(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
    language = models.CharField(_("language"), max_length=255, default="en")

    def __str__(self):
        return self.name


class PokemonAbility(TimestampedModel):
    slot = models.PositiveIntegerField(_("slot"))
    is_hidden = models.BooleanField(_("is hidden"), default=False)
    ability = models.CharField(_("ability"), max_length=255)

    class Meta:
        unique_together = ("slot", "ability", "is_hidden")
        verbose_name_plural = _("PokemonAbilities")

    def __str__(self):
        _str = self.ability

        if self.is_hidden:
            _str += " (hidden)"

        return _str


class PokemonFormType(TimestampedModel):
    slot = models.PositiveIntegerField(_("slot"))
    type = models.CharField(_("type"), max_length=255)

    class Meta:
        ordering = ("slot",)

    def __str__(self):
        return f"{self.type}"


class PokemonForm(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
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

    class Meta:
        ordering = ("pokemon__species__order", "order")

    def __str__(self):
        return self.name


class PokemonMove(TimestampedModel):
    move = models.ForeignKey(Move, on_delete=models.CASCADE)
    version_group_details = models.ManyToManyField(
        "PokemonMoveVersion", related_name="moves"
    )

    def __str__(self):
        return self.move.name


class PokemonMoveVersion(TimestampedModel):
    move_learn_method = models.CharField(_("move learn method"), max_length=255)
    version_group = models.ForeignKey("VersionGroup", on_delete=models.CASCADE)
    level_learned_at = models.PositiveIntegerField(_("level learned at"))
    order = models.PositiveIntegerField(_("order"), blank=True, null=True)


class PokemonSpecies(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
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

    class Meta:
        verbose_name_plural = _("PokemonSpecies")

    def __str__(self):
        return self.name


class PokemonSpeciesVariety(TimestampedModel):
    is_default = models.BooleanField(_("is default"), default=True)
    pokemon = models.ForeignKey(
        "Pokemon", on_delete=models.CASCADE, related_name="pokemon_species_varieties"
    )

    def __str__(self):
        return (
            f"{self.pokemon.name} (default)" if self.is_default else self.pokemon.name
        )


class PokemonSpeciesDexEntry(TimestampedModel):
    entry_number = models.PositiveIntegerField(_("entry number"))
    pokedex = models.CharField(_("pokédex"), max_length=255)

    def __str__(self):
        return f"{self.pokedex}#{self.entry_number}"


class PokemonStat(TimestampedModel):
    stat = models.CharField(_("stat"), max_length=255)
    effort = models.PositiveIntegerField(_("effort"))
    base_stat = models.PositiveIntegerField(_("base stat"))

    def __str__(self):
        return f"{self.stat}: {self.base_stat}"


class PokemonType(TimestampedModel):
    slot = models.PositiveIntegerField(_("slot"))
    type = models.CharField(_("type"), max_length=255)

    class Meta:
        ordering = ("slot",)

    def __str__(self):
        return f"{self.type}"


class Pokemon(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
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

    class Meta:
        ordering = ("order",)

    def __str__(self):
        return self.name


class Version(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
    version_group = models.ForeignKey("VersionGroup", on_delete=models.CASCADE)

    class Meta:
        ordering = ("version_group__order",)

    def __str__(self):
        return self.name


class VersionGameIndex(TimestampedModel):
    game_index = models.PositiveIntegerField(_("game index"))
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = _("VersionGameIndexes")

    def __str__(self):
        return f"{self.version}#{self.game_index}"


class VersionGroup(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
    generation = models.CharField(_("game generation"), max_length=255)
    order = models.PositiveIntegerField(_("order"))
    pokedexes = models.JSONField(_("pokédexes"), default=list)
    regions = models.JSONField(_("regions"), default=list)
    versions = models.JSONField(_("versions"), default=list)

    class Meta:
        ordering = ("order",)

    def __str__(self):
        return self.name
