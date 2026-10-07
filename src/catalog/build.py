"""Pacote do catálogo: os dados de referência que o app usa sem servidor
(arquitetura local-first, ishinydex#48), gerados por ``exportcatalog``.

Um JSON só, com chaves estáveis (ids da PokéAPI e o nº nacional da espécie),
para os dados do usuário poderem referenciar formas sem depender do banco que
gerou o pacote. Os sprites não vão junto: cada um é um caminho **relativo**
dentro do repositório PokeAPI/sprites (pasta ``sprites/``), que o build do
app baixa à parte.

Formato (``SCHEMA_VERSION``): mudanças incompatíveis sobem o número; campos
novos não.
"""

import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db.models import Prefetch
from django.utils import translation

from catalog.choices import specimen_options
from core.consts import TYPES_DICT
from home.models import HOME_TRANSFER_VERSIONS
from home.origin_marks import ORIGIN_MARK_VERSION_GROUPS
from home.services import default_forms
from pokedex.models import (
    Pokemon,
    PokemonForm,
    PokemonSpecies,
    PokemonSpeciesDexEntry,
    Version,
    VersionGroup,
)
from pokedex.renderers import HomeSpriteRenderer

# Os status base na ordem dos jogos (e do hexágono do app).
STAT_ORDER = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")


SCHEMA_VERSION = 1

# Shiny locks padrão, versionados no repositório (formas pelo nome): o banco
# de um CI não tem os locks cadastrados pelo app.
SHINY_LOCKS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/shiny_locks.json"
)

# Exclusivos de versão (formas pelo nome), versionados no repositório: a
# PokéAPI não tem esse dado. Fontes e critérios no próprio arquivo.
VERSION_EXCLUSIVES_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/version_exclusives.json"
)

# Lendários capturáveis fora das pokédex do jogo (Aventura Dinamax,
# Snacksworth): entram como pokédex especiais, sem número.
SPECIAL_ENCOUNTERS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/special_encounters.json"
)

# Nomes em pt-BR das pokédex dos jogos que recebem do HOME. Uma pokédex nova
# da PokéAPI sem nome aqui sai com o nome dela.
POKEDEX_LABELS = {
    "letsgo-kanto": "Kanto",
    "galar": "Galar",
    "isle-of-armor": "Ilha da Armadura",
    "crown-tundra": "Tundra Coroada",
    "original-sinnoh": "Sinnoh",
    "hisui": "Hisui",
    "paldea": "Paldea",
    "kitakami": "Kitakami",
    "blueberry": "Blueberry",
    "lumiose-city": "Lumiose",
    "hyperspace": "Hiperespaço",
}

# Grupos de versões das DLCs: a PokéAPI repete as pokédex deles no grupo do
# jogo, e é por eles que se sabe quais pokédex são de DLC.
DLC_VERSION_GROUPS = (
    "the-isle-of-armor",
    "the-crown-tundra",
    "the-teal-mask",
    "the-indigo-disk",
    "mega-dimension",
)

# A pokédex nacional do BDSP (liberada no pós-jogo): as espécies das gerações
# 1 a 4. A PokéAPI só lista a regional (``original-sinnoh``).
BDSP_GROUP = "brilliant-diamond-shining-pearl"
BDSP_NATIONAL = "bdsp-national"
BDSP_NATIONAL_LAST = 493


class CatalogError(Exception):
    pass


def _sprite(url: Path | str) -> str:
    """``/media/sprites/pokemon/1.png`` → ``pokemon/1.png``."""
    return PurePosixPath(url).relative_to(settings.SPRITES_URL).as_posix()


def _type_sprite(type_: str) -> str | None:
    type_id = TYPES_DICT.get(type_)
    if type_id is None:
        return None
    return (
        f"types/{settings.TYPE_SPRITES_DEFAULT_GEN}/"
        f"{settings.TYPE_SPRITES_DEFAULT_GAME}/small/{type_id}.png"
    )


def _form_sprites(form: PokemonForm) -> dict:
    if form.pokemon is None:
        return {"sprite": None, "shinySprite": None}
    return {
        "sprite": _sprite(HomeSpriteRenderer(form, "default").resolve_sprite_url()),
        "shinySprite": _sprite(HomeSpriteRenderer(form, "shiny").resolve_sprite_url()),
    }


def _forms() -> list[dict]:
    # Ordem nacional, desempatada pelo id da PokéAPI (e não pelo pk, que muda
    # de um banco para outro): o mesmo api-data gera sempre o mesmo arquivo.
    forms = (
        PokemonForm.objects.select_related("pokemon__species", "version_group")
        .prefetch_related("types")
        .order_by("pokemon__species__id", "form_order", "pokeapi_id")
    )
    return [
        {
            "id": f.pokeapi_id,
            "name": f.name,
            "formName": f.form_name,
            "pokemon": f.pokemon.pokeapi_id if f.pokemon else None,
            "formOrder": f.form_order,
            "isDefault": f.is_default,
            "isBattleOnly": f.is_battle_only,
            "isMega": f.is_mega,
            "versionGroup": f.version_group.name,
            "types": [t.type for t in sorted(f.types.all(), key=lambda t: t.slot)],
            **_form_sprites(f),
        }
        for f in forms
    ]


def _pokemon() -> list[dict]:
    pokemon = (
        Pokemon.objects.select_related("species")
        .prefetch_related("types", "abilities", "stats")
        .order_by("pokeapi_id")
    )

    def stat_position(stat) -> int:
        return STAT_ORDER.index(stat.stat) if stat.stat in STAT_ORDER else 99

    return [
        {
            "id": p.pokeapi_id,
            "name": p.name,
            "species": p.species.name if p.species else None,
            "isDefault": p.is_default,
            "height": p.height,
            "weight": p.weight,
            "types": [t.type for t in sorted(p.types.all(), key=lambda t: t.slot)],
            "abilities": [
                {"ability": a.ability, "slot": a.slot, "isHidden": a.is_hidden}
                for a in sorted(p.abilities.all(), key=lambda a: a.slot)
            ],
            "stats": [
                {"stat": s.stat, "base": s.base_stat, "effort": s.effort}
                for s in sorted(p.stats.all(), key=stat_position)
            ],
        }
        for p in pokemon
    ]


def _species() -> list[dict]:
    species = PokemonSpecies.objects.select_related(
        "evolves_from_species"
    ).prefetch_related(
        Prefetch(
            "pokedex_numbers",
            queryset=PokemonSpeciesDexEntry.objects.filter(pokedex="national"),
            to_attr="national_entries",
        )
    )
    return [
        {
            "name": s.name,
            "nationalNumber": next(
                (e.entry_number for e in getattr(s, "national_entries")),
                None,
            ),
            "generation": s.generation,
            "genderRate": s.gender_rate,
            "captureRate": s.capture_rate,
            "hatchCounter": s.hatch_counter,
            "isBaby": s.is_baby,
            "isLegendary": s.is_legendary,
            "isMythical": s.is_mythical,
            "evolvesFrom": (
                s.evolves_from_species.name if s.evolves_from_species else None
            ),
        }
        for s in species.order_by("id")
    ]


def _versions() -> tuple[list[dict], list[dict]]:
    mark_by_group = {
        group: mark
        for mark, groups in ORIGIN_MARK_VERSION_GROUPS.items()
        for group in groups
    }
    groups = [
        {
            "name": g.name,
            "generation": g.generation,
            "order": g.order,
            "versions": g.versions,
            "originMark": mark_by_group.get(g.name),
        }
        for g in VersionGroup.objects.order_by("order", "name")
    ]
    versions = [
        {
            "name": v.name,
            "versionGroup": v.version_group.name,
            "receivesFromHome": v.name in HOME_TRANSFER_VERSIONS,
        }
        for v in Version.objects.select_related("version_group").order_by(
            "version_group__order", "name"
        )
    ]
    return groups, versions


def _choices() -> dict:
    """As escolhas de ``/specimens/options/``, em pt-BR, com os sprites."""
    with translation.override("pt-br"):
        options = specimen_options()
    for ball in options["pokeball"]:
        ball["sprite"] = f"items/{ball['value']}.png"
    for type_ in options["type"]:
        type_["sprite"] = _type_sprite(type_["value"])
    return options


def _shiny_locks() -> list[dict]:
    """Os locks de ``SHINY_LOCKS_FILE``, com as formas trocadas pelos ids."""
    locks = json.loads(SHINY_LOCKS_FILE.read_text(encoding="utf-8"))
    names = {name for lock in locks for name in lock["forms"]}
    ids = dict(
        PokemonForm.objects.filter(name__in=names).values_list("name", "pokeapi_id")
    )
    if unknown := sorted(names - ids.keys()):
        raise CatalogError(f"shiny locks com formas desconhecidas: {unknown}")
    return [
        lock | {"forms": sorted(ids[name] for name in lock["forms"])} for lock in locks
    ]


def _pokedexes() -> tuple[list[dict], dict[str, set[str]]]:
    """As pokédex dos jogos que recebem do HOME, com as espécies (pelo nome)
    e o número em cada uma; e as espécies de cada grupo de versões."""
    home_groups = [
        g
        for g in VersionGroup.objects.order_by("order", "name")
        if any(v in HOME_TRANSFER_VERSIONS for v in g.versions)
    ]
    dlc_of = {
        dex: g.name
        for g in VersionGroup.objects.filter(name__in=DLC_VERSION_GROUPS)
        for dex in g.pokedexes
    }
    groups_of: dict[str, list[str]] = {}
    for g in home_groups:
        for dex in g.pokedexes:
            groups_of.setdefault(dex, []).append(g.name)
        if g.name == BDSP_GROUP:
            groups_of[BDSP_NATIONAL] = [g.name]

    entries: dict[str, list[list]] = {dex: [] for dex in groups_of}
    labels: dict[str, str] = {BDSP_NATIONAL: "Nacional"}
    for dex, number, species in (
        PokemonSpeciesDexEntry.objects.filter(pokedex__in=groups_of)
        .order_by("pokedex", "entry_number")
        .values_list("pokedex", "entry_number", "pokemon_species__name")
    ):
        entries[dex].append([species, number])
    if BDSP_NATIONAL in entries:
        entries[BDSP_NATIONAL] = [
            [species, number]
            for number, species in PokemonSpeciesDexEntry.objects.filter(
                pokedex="national", entry_number__lte=BDSP_NATIONAL_LAST
            )
            .order_by("entry_number")
            .values_list("entry_number", "pokemon_species__name")
        ]

    home = {g.name for g in home_groups}
    dlc_of = dlc_of | _special_encounters(home, groups_of, entries, labels)

    species_of_group: dict[str, set[str]] = {g.name: set() for g in home_groups}
    for dex, groups in groups_of.items():
        for group in groups:
            species_of_group[group].update(name for name, _ in entries[dex])
    pokedexes = [
        {
            "name": dex,
            "label": labels.get(dex)
            or POKEDEX_LABELS.get(dex, dex.replace("-", " ").title()),
            "versionGroups": groups,
            "dlc": dlc_of.get(dex),
            "entries": entries[dex],
        }
        for dex, groups in groups_of.items()
    ]
    return pokedexes, species_of_group


def _special_encounters(
    home: set[str],
    groups_of: dict[str, list[str]],
    entries: dict[str, list[list]],
    labels: dict[str, str],
) -> dict[str, str | None]:
    """Acrescenta as pokédex especiais de ``SPECIAL_ENCOUNTERS_FILE`` dos jogos
    que recebem do HOME (entradas sem número) e devolve a DLC de cada uma."""
    encounters = json.loads(SPECIAL_ENCOUNTERS_FILE.read_text(encoding="utf-8"))[
        "encounters"
    ]
    known = set(PokemonSpecies.objects.values_list("name", flat=True))
    dlc_of = {}
    for encounter in encounters:
        name, dlc = encounter["name"], encounter["dlc"]
        if unknown := sorted(set(encounter["species"]) - known):
            raise CatalogError(f"{name} com espécies desconhecidas: {unknown}")
        if dlc is not None and dlc not in DLC_VERSION_GROUPS:
            raise CatalogError(f"{name} com DLC desconhecida: {dlc}")
        if encounter["versionGroup"] not in home:
            continue
        groups_of[name] = [encounter["versionGroup"]]
        entries[name] = [[species, None] for species in encounter["species"]]
        labels[name] = encounter["label"]
        dlc_of[name] = dlc
    return dlc_of


def _version_exclusives(species_of_group: dict[str, set[str]]) -> list[dict]:
    """Os exclusivos de ``VERSION_EXCLUSIVES_FILE``, com as formas trocadas
    pelos ids. Falha com forma, versão ou DLC desconhecida, ou com forma cuja
    espécie não está em nenhuma pokédex do jogo (pega erro de digitação)."""
    groups = json.loads(VERSION_EXCLUSIVES_FILE.read_text(encoding="utf-8"))[
        "exclusives"
    ]
    names = {name for group in groups for name in group["forms"]}
    forms = {
        name: (pokeapi_id, species)
        for name, pokeapi_id, species in PokemonForm.objects.filter(
            name__in=names
        ).values_list("name", "pokeapi_id", "pokemon__species__name")
    }
    if unknown := sorted(names - forms.keys()):
        raise CatalogError(f"exclusivos com formas desconhecidas: {unknown}")
    group_of = dict(Version.objects.values_list("name", "version_group__name"))
    result = []
    for group in groups:
        version, dlc = group["version"], group["dlc"]
        species = species_of_group.get(group_of.get(version, ""))
        if species is None:
            raise CatalogError(f"exclusivos de versão sem pokédex: {version}")
        if dlc is not None and dlc not in DLC_VERSION_GROUPS:
            raise CatalogError(f"exclusivos com DLC desconhecida: {dlc}")
        if outside := [n for n in group["forms"] if forms[n][1] not in species]:
            raise CatalogError(
                f"exclusivos de {version} fora das pokédex do jogo: {outside}"
            )
        result.append(
            {
                "version": version,
                "dlc": dlc,
                "forms": [forms[name][0] for name in group["forms"]],
            }
        )
    return result


def build_catalog(version: str) -> dict:
    groups, versions = _versions()
    pokedexes, species_of_group = _pokedexes()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "version": version,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "spritesRepository": "https://github.com/PokeAPI/sprites",
        "forms": _forms(),
        "pokemon": _pokemon(),
        "species": _species(),
        "versionGroups": groups,
        "versions": versions,
        # Ordem e conjunto de formas de um dex padrão novo (ids das formas).
        "defaultDex": [f.pokeapi_id for f in default_forms()],
        "choices": _choices(),
        "shinyLocks": _shiny_locks(),
        # Em que pokédex de cada jogo do HOME cada espécie está, e as formas
        # exclusivas de uma versão (saves compatíveis, nas caçadas).
        "pokedexes": pokedexes,
        "versionExclusives": _version_exclusives(species_of_group),
    }
