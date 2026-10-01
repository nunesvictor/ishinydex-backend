"""Helpers para criação de objetos nos testes.

Os models do pokedex possuem muitos campos obrigatórios vindos da PokéAPI; estas
funções preenchem valores padrão razoáveis e permitem sobrescrever apenas o que
importa para cada teste.
"""

from itertools import count

from home.models import Box, OriginalTrainer, PersonalDex, Specimen
from pokedex.models import (
    Pokemon,
    PokemonAbility,
    PokemonForm,
    PokemonFormType,
    PokemonSpecies,
    PokemonSpeciesDexEntry,
    PokemonSpeciesVariety,
    PokemonStat,
    PokemonType,
    ShinyLock,
    Version,
    VersionGroup,
)

_seq = count(1)


def _next() -> int:
    return next(_seq)


# Último nº da dex nacional de cada geração (I a VIII; o resto é IX).
_GENERATION_ENDS = (151, 251, 386, 493, 649, 721, 809, 905)
_ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix")


def generation_of(national_number: int) -> str:
    """Geração da espécie pelo nº nacional, no formato da PokéAPI."""
    index = sum(national_number > end for end in _GENERATION_ENDS)
    return f"generation-{_ROMAN[index]}"


def make_version_group(**kwargs) -> VersionGroup:
    n = _next()
    defaults = {
        "name": f"version-group-{n}",
        "generation": "generation-i",
        "order": n,
    }
    return VersionGroup.objects.create(**(defaults | kwargs))


def make_version(**kwargs) -> Version:
    defaults = {"name": f"version-{_next()}"}

    if "version_group" not in kwargs:
        defaults["version_group"] = make_version_group()

    return Version.objects.create(**(defaults | kwargs))


def make_species(**kwargs) -> PokemonSpecies:
    n = _next()
    defaults = {
        "name": f"species-{n}",
        "order": n,
        "gender_rate": 4,
        "capture_rate": 45,
        "base_happiness": 70,
        "hatch_counter": 20,
        "growth_rate": "medium-slow",
        "color": "green",
        "shape": "quadruped",
        "generation": "generation-i",
    }
    return PokemonSpecies.objects.create(**(defaults | kwargs))


def make_pokemon(species: PokemonSpecies | None = None, **kwargs) -> Pokemon:
    n = _next()
    defaults = {
        "name": species.name if species else f"pokemon-{n}",
        "pokeapi_id": n,
        "height": 7,
        "weight": 69,
        "order": n,
        "species": species,
    }
    return Pokemon.objects.create(**(defaults | kwargs))


def make_form(pokemon: Pokemon | None = None, **kwargs) -> PokemonForm:
    n = _next()
    pokemon = pokemon if pokemon is not None else make_pokemon()
    defaults = {
        "name": pokemon.name,
        "pokeapi_id": pokemon.pokeapi_id,
        "order": n,
        "form_order": 1,
        "form_name": "",
        "is_default": True,
        "pokemon": pokemon,
    }

    if "version_group" not in kwargs:
        defaults["version_group"] = make_version_group()

    return PokemonForm.objects.create(**(defaults | kwargs))


def make_full_pokemon(
    name: str,
    pokeapi_id: int,
    *,
    types: tuple[str, ...] = ("grass",),
    abilities: tuple[str, ...] = (),
    has_gender_differences: bool = False,
    national_dex: int | None = None,
) -> tuple[PokemonSpecies, Pokemon, PokemonForm]:
    """Cria espécie + pokémon + forma padrão já interligados."""
    species = make_species(
        name=name,
        has_gender_differences=has_gender_differences,
        generation=generation_of(national_dex or pokeapi_id),
    )
    pokemon = make_pokemon(species, name=name, pokeapi_id=pokeapi_id)
    form = make_form(pokemon, name=name)

    species.varieties.add(
        PokemonSpeciesVariety.objects.create(is_default=True, pokemon=pokemon)
    )

    for slot, type_ in enumerate(types, start=1):
        pokemon.types.add(PokemonType.objects.create(slot=slot, type=type_))
        form.types.add(PokemonFormType.objects.create(slot=slot, type=type_))

    for slot, ability in enumerate(abilities, start=1):
        pokemon.abilities.add(
            PokemonAbility.objects.get_or_create(
                slot=slot, ability=ability, is_hidden=False
            )[0]
        )

    if national_dex is not None:
        species.pokedex_numbers.add(
            PokemonSpeciesDexEntry.objects.create(
                entry_number=national_dex, pokedex="national"
            )
        )

    return species, pokemon, form


def make_stat(pokemon: Pokemon, stat: str, base_stat: int) -> PokemonStat:
    obj = PokemonStat.objects.create(stat=stat, effort=0, base_stat=base_stat)
    pokemon.stats.add(obj)
    return obj


def make_shinylock(*forms: PokemonForm, **kwargs) -> ShinyLock:
    defaults = {"caption": f"lock-{_next()}"}
    lock = ShinyLock.objects.create(**(defaults | kwargs))
    lock.forms.add(*forms)
    return lock


def make_box(**kwargs) -> Box:
    defaults = {"name": f"HOME {_next()}"}
    return Box.objects.create(**(defaults | kwargs))


def make_personal_dex(*forms: PokemonForm, **kwargs) -> PersonalDex:
    defaults = {"name": f"dex-{_next()}"}
    dex = PersonalDex.objects.create(**(defaults | kwargs))
    dex.forms.add(*forms)
    return dex


def make_ot(**kwargs) -> OriginalTrainer:
    n = _next()
    defaults = {"name": f"Trainer{n}", "trainer_id": f"{n:06d}"}
    return OriginalTrainer.objects.create(**(defaults | kwargs))


def make_specimen(form: PokemonForm, **kwargs) -> Specimen:
    return Specimen.objects.create(form=form, **kwargs)
