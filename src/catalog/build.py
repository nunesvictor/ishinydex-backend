"""Pacote do catálogo: os dados de referência que o app usa sem servidor
(arquitetura local-first, ishinydex#48), gerados por ``exportcatalog``.

Um JSON só, com chaves estáveis (ids da PokéAPI e o nº nacional da espécie),
para os dados do usuário poderem referenciar formas sem depender do banco que
gerou o pacote. Os sprites não vão junto: cada um é um caminho **relativo**
dentro do repositório PokeAPI/sprites (pasta ``sprites/``), que o build do
app baixa à parte.

Formato (``SCHEMA_VERSION``): mudanças incompatíveis sobem o número; campos
novos não.

Textos (backend#105): cada rótulo sai em pt-BR em ``label`` (o que o app
antigo lê) e em todos os idiomas em ``labels`` (``{"en": …, "pt-BR": …}``);
o ``note`` das odds, em ``note`` e ``notes``. Nos arquivos de dados, os
textos já vêm nos dois idiomas; no código, pelo gettext.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.db.models import Prefetch
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from catalog.choices import specimen_options
from core.consts import TYPES_DICT
from home.models import HOME_ORIGIN_VERSIONS, HOME_TRANSFER_VERSIONS
from home.origin_marks import ORIGIN_MARK_VERSION_GROUPS
from home.services import default_forms
from pokedex.models import (
    EvolutionMethod,
    Move,
    MoveMachine,
    Pokemon,
    PokemonForm,
    PokemonMoveLearn,
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

# Formas presentes em cada jogo, para as espécies com forma regional (a
# pokédex da PokéAPI é por espécie: sem isso, a Ponyta de Galar estaria em
# Legends: Arceus).
REGIONAL_FORMS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/regional_forms.json"
)

# Evoluções entre formas das famílias com forma regional (#121): a PokéAPI
# só tem a evolução entre espécies (o Rattata de Alola vira o Raticate de
# Alola, e não o comum).
REGIONAL_EVOLUTIONS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/regional_evolutions.json"
)

# Frases próprias e links "Veja mais" dos métodos de evolução bizarros (#133),
# e as correções do que a PokéAPI não diz (a versão do Cosmoem).
EVOLUTION_METHODS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/evolution_methods.json"
)
# Gatilhos e condições que o app sabe descrever. Um novo na PokéAPI falha o
# catálogo: ou o app aprende a descrevê-lo, ou ele ganha uma frase curada.
EVOLUTION_TRIGGERS = {
    "level-up",
    "use-item",
    "trade",
    "spin",
    "in-battle-level-up",
    "recoil-damage",
    "use-move",
    "gimmighoul-coins",
    "tower-of-darkness",
    "tower-of-waters",
    "meltan-candies",
    "three-critical-hits",
    "three-defeated-bisharp",
    "take-damage",
    "shed",
    "agile-style-move",
    "strong-style-move",
}
EVOLUTION_CONDITIONS = {
    "min_level",
    "time_of_day",
    "held_item",
    "item",
    "location",
    "min_happiness",
    "known_move",
    "known_move_type",
    "gender",
    "region",
    "near_special_rock",
    "used_move",
    "min_move_count",
    "min_steps",
    "min_damage_taken",
    "relative_physical_stats",
    "allowed_natures",
    "needs_overworld_rain",
    "trade_species",
    "min_beauty",
    "min_affection",
    "needs_multiplayer",
    "turn_upside_down",
    "party_type",
    "party_species",
    "condition_expression",
}
# O tipo de recurso de cada condição com nome próprio (os nomes em inglês
# saem em ``names``).
EVOLUTION_NAME_KINDS = {
    "item": "items",
    "held_item": "items",
    "known_move": "moves",
    "used_move": "moves",
    "location": "locations",
}
GENDERS = {1: "female", 2: "male"}

# Modos de aprender um golpe que o app sabe mostrar (os quatro principais e
# os de "Outros", #36). Um novo na PokéAPI falha o pacote dos golpes.
MOVE_LEARN_METHODS = (
    "level-up",
    "machine",
    "egg",
    "tutor",
    "light-ball-egg",
    "form-change",
    "zygarde-cube",
    "stadium-surfing-pikachu",
    "train",
    "xd-purification",
)

# Formas que não podem ser obtidas shiny em cada jogo (Solgaleo em Scarlet).
GAME_SHINY_LOCKS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/game_shiny_locks.json"
)

# Formas que podem aparecer como alfa em cada jogo (motivo "Sem alfa" das
# Caçadas, #123).
ALPHA_FORMS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/alpha_forms.json"
)

# Espécies que o jogo aceita pelo HOME, fora das pokédex dele, e que só se
# caçam por ovo (o Phione no Scarlet/Violet, #128).
HOME_EGGS_FILE = Path(__file__).resolve().parent.parent / "pokedex/data/home_eggs.json"

# Métodos de shiny hunt por jogo (registro da caçada no espécime, #103).
SHINY_METHODS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/shiny_methods.json"
)
SHINY_METHOD_UNITS = {
    "encounters",
    "hours",
    "resets",
    "eggs",
    "chains",
    "runs",
    "raids",
    "hordes",
    "combo",
}

# Jogos só de ida que deixam de chegar ao HOME numa data (fechamento do
# Pokémon Bank, #114).
HOME_CUTOFFS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/home_cutoffs.json"
)

# Odds de shiny por método e jogo de save (odds das caçadas, #113).
SHINY_ODDS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/shiny_odds.json"
)
SHINY_ODDS_KINDS = {"rolls", "chance", "dexnav"}
SHINY_ODDS_BASES = {4096, 8192}

# Lendários capturáveis fora das pokédex do jogo (Aventura Dinamax,
# Snacksworth): entram como pokédex especiais, sem número.
SPECIAL_ENCOUNTERS_FILE = (
    Path(__file__).resolve().parent.parent / "pokedex/data/special_encounters.json"
)

# Idiomas dos rótulos do catálogo (``labels``), com o código do Django de
# cada um. O ``label`` continua em pt-BR, para o app antigo.
LANGUAGES = {"en": "en", "pt-BR": "pt-br"}

# Nomes das pokédex dos jogos ligados ao HOME (traduzidos pelo gettext; os
# nomes próprios ficam iguais). Uma pokédex nova da PokéAPI sem nome aqui
# sai com o nome dela.
POKEDEX_LABELS = {
    "kanto": "Kanto",
    "kalos-central": _("Central Kalos"),
    "kalos-coastal": _("Coastal Kalos"),
    "kalos-mountain": _("Mountain Kalos"),
    "updated-hoenn": "Hoenn",
    "original-alola": "Alola",
    "original-melemele": "Melemele",
    "original-akala": "Akala",
    "original-ulaula": "Ula'ula",
    "original-poni": "Poni",
    "updated-alola": "Alola",
    "updated-melemele": "Melemele",
    "updated-akala": "Akala",
    "updated-ulaula": "Ula'ula",
    "updated-poni": "Poni",
    "letsgo-kanto": "Kanto",
    "galar": "Galar",
    "isle-of-armor": _("Isle of Armor"),
    "crown-tundra": _("Crown Tundra"),
    "original-sinnoh": "Sinnoh",
    "hisui": "Hisui",
    "paldea": "Paldea",
    "kitakami": "Kitakami",
    "blueberry": "Blueberry",
    "lumiose-city": "Lumiose",
    "hyperspace": _("Hyperspace"),
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


def _both(label) -> dict[str, str]:
    """O rótulo (texto ou gettext) em cada idioma de ``LANGUAGES``."""
    result = {}
    for lang, code in LANGUAGES.items():
        with translation.override(code):
            result[lang] = str(label)
    return result


def _text(where: str, value) -> dict[str, str]:
    """Um texto dos arquivos de dados: ``{"en": …, "pt-BR": …}``. Falha se
    faltar um idioma (ou sobrar outro) ou se algum vier vazio."""
    if (
        not isinstance(value, dict)
        or set(value) != set(LANGUAGES)
        or not all(isinstance(v, str) and v for v in value.values())
    ):
        raise CatalogError(f"texto sem os idiomas {sorted(LANGUAGES)} em {where}")
    return value


def _labeled(key: str, texts: dict[str, str]) -> dict:
    """``key`` em pt-BR (o app antigo lê esse) e ``key + "s"`` com todos os
    idiomas: ``label`` → ``label`` e ``labels``."""
    return {key: texts["pt-BR"], f"{key}s": texts}


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


def _home_cutoffs() -> dict[str, str]:
    """Versão → ``homeUntil`` de ``HOME_CUTOFFS_FILE``. Falha com versão
    desconhecida, que não seja só de ida, repetida, ou com data que não seja
    ISO 8601 em UTC."""
    cutoffs = json.loads(HOME_CUTOFFS_FILE.read_text(encoding="utf-8"))["cutoffs"]
    one_way = set(HOME_ORIGIN_VERSIONS) - set(HOME_TRANSFER_VERSIONS)
    known = set(Version.objects.values_list("name", flat=True))
    result: dict[str, str] = {}
    for cutoff in cutoffs:
        until = cutoff["homeUntil"]
        try:
            parsed = datetime.fromisoformat(until)
        except ValueError:
            parsed = None
        if parsed is None or parsed.utcoffset() != timedelta(0):
            raise CatalogError(f"data de corte inválida (use UTC): {until}")
        for version in cutoff["versions"]:
            if version not in one_way or version not in known:
                raise CatalogError(f"corte em versão que não é só de ida: {version}")
            if version in result:
                raise CatalogError(f"corte repetido: {version}")
            result[version] = until
    return result


# O Pokémon GO como jogo (ishinydex-backend#131): a PokéAPI não tem uma
# versão dele. Entra só na lista de jogos, sem grupo de versão (o app o
# põe no topo da lista); como o FRLG, só envia para o HOME.
GO_VERSION = {
    "name": "pokemon-go",
    "versionGroup": "pokemon-go",
    "receivesFromHome": False,
}


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
    cutoffs = _home_cutoffs()
    versions = [
        {
            "name": v.name,
            "versionGroup": v.version_group.name,
            "receivesFromHome": v.name in HOME_TRANSFER_VERSIONS,
            # Só nos jogos com data de corte (chave aditiva).
            **({"homeUntil": cutoffs[v.name]} if v.name in cutoffs else {}),
        }
        for v in Version.objects.select_related("version_group").order_by(
            "version_group__order", "name"
        )
    ]
    return groups, [GO_VERSION, *versions]


def _choices() -> dict:
    """As escolhas de ``/specimens/options/``, com o rótulo em pt-BR, os
    rótulos em cada idioma (``labels``) e os sprites."""
    by_lang = {}
    for lang, code in LANGUAGES.items():
        with translation.override(code):
            by_lang[lang] = specimen_options()
    options = by_lang["pt-BR"]
    for key, items in options.items():
        for i, item in enumerate(items):
            item["labels"] = {
                lang: str(by_lang[lang][key][i]["label"]) for lang in LANGUAGES
            }
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
    """As pokédex dos jogos ligados ao HOME (inclusive os só de ida, como o
    FRLG e os do Bank), com as espécies (pelo nome) e o número em cada uma;
    e as espécies de cada grupo de versões."""
    home_groups = [
        g
        for g in VersionGroup.objects.order_by("order", "name")
        if any(v in HOME_ORIGIN_VERSIONS for v in g.versions)
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
    labels: dict[str, dict[str, str]] = {BDSP_NATIONAL: _both(_("National"))}
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
            **_labeled(
                "label",
                labels.get(dex)
                or _both(POKEDEX_LABELS.get(dex, dex.replace("-", " ").title())),
            ),
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
    labels: dict[str, dict[str, str]],
) -> dict[str, str | None]:
    """Acrescenta as pokédex especiais de ``SPECIAL_ENCOUNTERS_FILE`` dos jogos
    ligados ao HOME (entradas sem número) e devolve a DLC de cada uma."""
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
        label = _text(name, encounter["label"])
        if encounter["versionGroup"] not in home:
            continue
        groups_of[name] = [encounter["versionGroup"]]
        entries[name] = [[species, None] for species in encounter["species"]]
        labels[name] = label
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


def _form_ids(names: set[str], what: str) -> dict[str, tuple[int, str]]:
    """Nome da forma → (id, espécie); falha com forma desconhecida."""
    forms = {
        name: (pokeapi_id, species)
        for name, pokeapi_id, species in PokemonForm.objects.filter(
            name__in=names
        ).values_list("name", "pokeapi_id", "pokemon__species__name")
    }
    if unknown := sorted(names - forms.keys()):
        raise CatalogError(f"{what} com formas desconhecidas: {unknown}")
    return forms


def _game_forms(species_of_group: dict[str, set[str]]) -> list[dict]:
    """As formas de ``REGIONAL_FORMS_FILE``, trocadas pelos ids."""
    return _forms_by_group(REGIONAL_FORMS_FILE, "formas por jogo", species_of_group)


def _alpha_forms(species_of_group: dict[str, set[str]]) -> list[dict]:
    """As formas de ``ALPHA_FORMS_FILE``, trocadas pelos ids."""
    return _forms_by_group(ALPHA_FORMS_FILE, "alfas", species_of_group)


def _home_eggs(species_of_group: dict[str, set[str]]) -> list[dict]:
    """As formas de ``HOME_EGGS_FILE``, trocadas pelos ids. Falha com forma
    ou grupo desconhecido, ou com espécie que já está numa pokédex do jogo
    (aí ela não precisa da lista)."""
    games = json.loads(HOME_EGGS_FILE.read_text(encoding="utf-8"))["games"]
    forms = _form_ids({n for game in games for n in game["forms"]}, "ovos pelo HOME")
    result = []
    for game in games:
        group = game["versionGroup"]
        species = species_of_group.get(group)
        if species is None:
            raise CatalogError(f"ovos pelo HOME sem pokédex: {group}")
        if inside := [n for n in game["forms"] if forms[n][1] in species]:
            raise CatalogError(f"ovos pelo HOME já nas pokédex de {group}: {inside}")
        result.append(
            {
                "versionGroup": group,
                "forms": sorted(forms[name][0] for name in game["forms"]),
            }
        )
    return result


def _forms_by_group(
    file: Path, what: str, species_of_group: dict[str, set[str]]
) -> list[dict]:
    """As formas de cada grupo de versões de ``file``, trocadas pelos ids.
    Falha com forma ou grupo desconhecido, ou com espécie fora das pokédex
    do jogo."""
    games = json.loads(file.read_text(encoding="utf-8"))["games"]
    forms = _form_ids({n for game in games for n in game["forms"]}, what)
    result = []
    for game in games:
        group = game["versionGroup"]
        species = species_of_group.get(group)
        if species is None:
            raise CatalogError(f"{what} sem pokédex: {group}")
        if outside := [n for n in game["forms"] if forms[n][1] not in species]:
            raise CatalogError(f"{what} de {group} fora das pokédex do jogo: {outside}")
        result.append(
            {
                "versionGroup": group,
                "forms": sorted(forms[name][0] for name in game["forms"]),
            }
        )
    return result


def _form_evolutions() -> dict:
    """As evoluções de ``REGIONAL_EVOLUTIONS_FILE``, com os ids das formas.
    Falha com forma desconhecida, aresta repetida ou que não bate com o
    ``evolves_from_species`` das espécies."""
    data = json.loads(REGIONAL_EVOLUTIONS_FILE.read_text(encoding="utf-8"))
    edges = [(e["from"], e["to"]) for e in data["evolutions"]]
    alone = data["withoutEvolution"]
    if len(set(edges)) != len(edges):
        raise CatalogError("evoluções regionais repetidas")
    names = {n for edge in edges for n in edge} | set(alone)
    forms = _form_ids(names, "evoluções regionais")
    evolves_from = dict(
        PokemonSpecies.objects.filter(
            name__in={species for _, species in forms.values()}
        ).values_list("name", "evolves_from_species__name")
    )
    if wrong := [
        f"{a}->{b}" for a, b in edges if evolves_from[forms[b][1]] != forms[a][1]
    ]:
        raise CatalogError(f"evoluções regionais fora da espécie: {wrong}")
    return {
        "evolutions": sorted([forms[a][0], forms[b][0]] for a, b in edges),
        "withoutEvolution": sorted(forms[n][0] for n in alone),
    }


def _camel(key: str) -> str:
    """``min_level`` → ``minLevel``."""
    head, *rest = key.split("_")
    return head + "".join(word.title() for word in rest)


def _evolution_method(method: EvolutionMethod) -> dict:
    """Um método no formato do catálogo: o jogo, se é o padrão, o gatilho e
    as condições em camelCase. Da ``condition_expression`` sai só a chance
    (``chance``: 50 no Wurmple); o gênero vira ``female``/``male``."""
    result = {
        "versionGroup": method.version_group.name,
        "default": method.is_default,
        "trigger": method.trigger,
    }
    for key, value in method.conditions.items():
        if key == "condition_expression":
            if value["chance"] is not None:
                result["chance"] = value["chance"]
        elif key == "gender":
            result["gender"] = GENDERS[value]
        else:
            result[_camel(key)] = value
    return result


def _evolution_methods() -> dict:
    """Os métodos de evolução da PokéAPI por par de formas (``from`` e ``to``
    com os ids; sem forma na PokéAPI, a padrão da espécie), os nomes em
    inglês dos itens, golpes e lugares citados e, de
    ``EVOLUTION_METHODS_FILE``, as frases e os links por par de espécies.

    Falha com gatilho ou condição desconhecidos, com um par de formas sem
    exatamente um método padrão, com uma condição que o app não descreve
    (``condition_expression`` sem chance, o giro do Milcery) sem frase
    curada, ou com curadoria de um par sem métodos."""
    methods = list(
        EvolutionMethod.objects.select_related(
            "from_species", "to_species", "version_group"
        ).order_by("version_group__order", "to_species_id", "order")
    )
    if unknown := sorted({m.trigger for m in methods} - EVOLUTION_TRIGGERS):
        raise CatalogError(f"gatilhos de evolução desconhecidos: {unknown}")
    if unknown := sorted(
        {k for m in methods for k in m.conditions} - EVOLUTION_CONDITIONS
    ):
        raise CatalogError(f"condições de evolução desconhecidas: {unknown}")

    default_form = dict(
        PokemonForm.objects.filter(is_default=True, pokemon__is_default=True)
        .values_list("pokemon__species__name", "name")
        .order_by()
    )

    def ends(m: EvolutionMethod) -> tuple[str, str]:
        return (
            m.from_form or default_form[m.from_species.name],
            m.to_form or default_form[m.to_species.name],
        )

    forms = _form_ids({n for m in methods for n in ends(m)}, "métodos de evolução")
    data = json.loads(EVOLUTION_METHODS_FILE.read_text(encoding="utf-8"))
    curated = {}
    for entry in data["methods"]:
        pair = (entry["from"], entry["to"])
        where = f"{pair[0]}->{pair[1]}"
        if pair in curated:
            raise CatalogError(f"curadoria de evolução repetida: {where}")
        if not entry["link"].startswith("https://bulbapedia.bulbagarden.net/"):
            raise CatalogError(f"link fora da Bulbapedia em {where}")
        curated[pair] = {
            **_labeled("text", _text(where, entry["text"])),
            "link": entry["link"],
        }

    by_edge: dict[tuple[str, str], list[EvolutionMethod]] = {}
    for m in methods:
        by_edge.setdefault(ends(m), []).append(m)
    species_pairs = {(m.from_species.name, m.to_species.name) for m in methods}
    if unused := sorted(f"{a}->{b}" for a, b in curated.keys() - species_pairs):
        raise CatalogError(f"curadoria de evolução sem métodos: {unused}")

    names: dict[str, dict[str, str]] = {
        kind: {} for kind in ("items", "moves", "locations")
    }
    edges = []
    for (a, b), edge in by_edge.items():
        where = f"{a}->{b}"
        if sum(m.is_default for m in edge) != 1:
            raise CatalogError(f"evolução sem um método padrão: {where}")
        pair = (edge[0].from_species.name, edge[0].to_species.name)
        if pair not in curated and any(
            m.conditions.get("condition_expression", {}).get("chance", 0) is None
            for m in edge
        ):
            raise CatalogError(f"evolução sem frase curada: {where}")
        for m in edge:
            for key, kind in EVOLUTION_NAME_KINDS.items():
                if key in m.conditions:
                    slug = m.conditions[key]
                    names[kind][slug] = m.labels[slug]
        edges.append(
            {
                "from": forms[a][0],
                "to": forms[b][0],
                "methods": [_evolution_method(m) for m in edge],
                **curated.get(pair, {}),
            }
        )
    edges.sort(key=lambda e: (e["from"], e["to"]))
    return {
        "edges": edges,
        "names": {kind: dict(sorted(n.items())) for kind, n in names.items()},
    }


def _game_shiny_locks(species_of_group: dict[str, set[str]]) -> list[dict]:
    """Os locks de ``GAME_SHINY_LOCKS_FILE``, com os ids das formas. Falha
    com forma ou versão desconhecida, ou com espécie fora das pokédex."""
    locks = json.loads(GAME_SHINY_LOCKS_FILE.read_text(encoding="utf-8"))["locks"]
    forms = _form_ids({n for lock in locks for n in lock["forms"]}, "locks por jogo")
    group_of = dict(Version.objects.values_list("name", "version_group__name"))
    result = []
    for lock in locks:
        version = lock["version"]
        species = species_of_group.get(group_of.get(version, ""))
        if species is None:
            raise CatalogError(f"locks por jogo sem pokédex: {version}")
        if outside := [n for n in lock["forms"] if forms[n][1] not in species]:
            raise CatalogError(
                f"locks de {version} fora das pokédex do jogo: {outside}"
            )
        result.append(
            {"version": version, "forms": sorted(forms[n][0] for n in lock["forms"])}
        )
    return result


def _shiny_methods() -> list[dict]:
    """Os métodos de ``SHINY_METHODS_FILE``. Falha com id repetido, sem
    unidade, com unidade fora de ``SHINY_METHOD_UNITS`` ou com versão
    desconhecida."""
    methods = json.loads(SHINY_METHODS_FILE.read_text(encoding="utf-8"))["methods"]
    known = set(Version.objects.values_list("name", flat=True))
    seen: set[str] = set()
    result = []
    for method in methods:
        id_ = method["id"]
        if id_ in seen:
            raise CatalogError(f"método de shiny repetido: {id_}")
        seen.add(id_)
        units = method["units"]
        if not units or not set(units) <= SHINY_METHOD_UNITS:
            raise CatalogError(f"unidades inválidas em {id_}: {units}")
        if unknown := [v for v in method["versions"] if v not in known]:
            raise CatalogError(f"versões desconhecidas em {id_}: {unknown}")
        result.append(
            {
                "id": id_,
                **_labeled("label", _text(id_, method["label"])),
                "units": units,
                "versions": method["versions"],
            }
        )
    return result


def _check_chain(where: str, kind: str, chain: dict) -> None:
    steps = chain["steps"]
    field = "odds" if kind == "chance" else "rolls"
    starts = [step["from"] for step in steps]
    if not steps or starts[0] != 0 or starts != sorted(set(starts)):
        raise CatalogError(f"cadeia de {where} fora de ordem: {starts}")
    if any(step.get(field) is None for step in steps):
        raise CatalogError(f"cadeia de {where} sem {field}")


def _check_modifiers(where: str, modifiers: list[dict]) -> dict[str, int]:
    """Confere os modificadores; devolve id → quantidade de opções (0 para
    os numéricos)."""
    sizes: dict[str, int] = {}
    for modifier in modifiers:
        id_ = modifier["id"]
        if id_ in sizes:
            raise CatalogError(f"modificador repetido em {where}: {id_}")
        if modifier["type"] == "choice":
            if not modifier["options"]:
                raise CatalogError(f"modificador sem opções em {where}: {id_}")
            sizes[id_] = len(modifier["options"])
        elif modifier["type"] == "number":
            if modifier["min"] >= modifier["max"]:
                raise CatalogError(f"faixa inválida em {where}: {id_}")
            sizes[id_] = 0
        else:
            raise CatalogError(f"tipo de modificador inválido em {where}: {id_}")
        if when := modifier.get("when"):
            if not 0 <= when["option"] < sizes.get(when["modifier"], 0):
                raise CatalogError(f"condição inválida em {where}: {id_}")
    return sizes


def _check_table(where: str, table: dict, sizes: dict[str, int]) -> None:
    rows, columns = sizes.get(table["rows"], 0), sizes.get(table["columns"], 0)
    odds = table["odds"]
    if not rows or not columns or len(odds) != rows:
        raise CatalogError(f"tabela de {where} não bate com os modificadores")
    if any(len(row) != columns for row in odds):
        raise CatalogError(f"tabela de {where} não bate com os modificadores")


def _modifier(where: str, modifier: dict) -> dict:
    """O modificador com o rótulo dele e o das opções nos idiomas."""
    result = modifier | _labeled("label", _text(where, modifier["label"]))
    if "options" in modifier:
        result["options"] = [
            option | _labeled("label", _text(where, option["label"]))
            for option in modifier["options"]
        ]
    return result


def _shiny_odds(methods: list[dict]) -> list[dict]:
    """As regras de ``SHINY_ODDS_FILE``, com os ids das formas em que o
    Charm não vale. Falha com método ou versão fora de ``SHINY_METHODS_FILE``,
    par método × versão repetido, tipo ou base inválidos, cadeia fora de
    ordem, modificador inválido ou tabela que não bate com os modificadores."""
    rules = json.loads(SHINY_ODDS_FILE.read_text(encoding="utf-8"))["rules"]
    versions_of = {m["id"]: set(m["versions"]) for m in methods}
    forms = _form_ids(
        {n for rule in rules for n in rule["charmExceptForms"]}, "odds de shiny"
    )
    seen: set[tuple[str, str]] = set()
    result = []
    for rule in rules:
        method, kind = rule["method"], rule["kind"]
        where = f"{method} ({', '.join(rule['versions'])})"
        if method not in versions_of:
            raise CatalogError(f"odds de método desconhecido: {method}")
        if outside := [v for v in rule["versions"] if v not in versions_of[method]]:
            raise CatalogError(f"odds de {method} fora dos jogos do método: {outside}")
        for version in rule["versions"]:
            if (method, version) in seen:
                raise CatalogError(f"odds repetidas: {method} em {version}")
            seen.add((method, version))
        if kind not in SHINY_ODDS_KINDS or rule["base"] not in SHINY_ODDS_BASES:
            raise CatalogError(f"tipo ou base inválidos em {where}")
        if kind == "chance":
            if not ("odds" in rule or "chain" in rule or "table" in rule):
                raise CatalogError(f"odds sem chance em {where}")
        elif not rule.get("rolls"):
            raise CatalogError(f"odds sem sorteios em {where}")
        if chain := rule.get("chain"):
            _check_chain(where, kind, chain)
        sizes = _check_modifiers(where, rule["modifiers"])
        if table := rule.get("table"):
            _check_table(where, table, sizes)
        exported = {k: v for k, v in rule.items() if k != "sources"}
        if "note" in rule:
            exported |= _labeled("note", _text(where, rule["note"]))
        exported["modifiers"] = [_modifier(where, m) for m in rule["modifiers"]]
        exported["charmExceptForms"] = sorted(
            forms[n][0] for n in rule["charmExceptForms"]
        )
        result.append(exported)
    return result


def moves_file_name(version: str) -> str:
    """O arquivo dos golpes de uma versão do catálogo, com a versão no nome
    (``catalog-2026.11.02`` → ``moves-2026.11.02.json``): o conteúdo de um
    nome nunca muda, e o app guarda o arquivo sem conferir de novo."""
    return f"moves-{version.removeprefix('catalog-')}.json"


def build_moves(version: str) -> dict:
    """O pacote dos golpes (#134), à parte do catálogo: o app só o baixa ao
    abrir a aba Golpes ou a busca (frontend#36).

    Compacto, com índices no lugar dos nomes repetidos:

    - ``moves``: os golpes que algum pokémon aprende, em ordem de nome; o
      índice na lista é o que ``learnsets`` e ``machines`` usam. Os valores
      de jogos antigos ficam em ``past`` (valem nos grupos de versões
      anteriores ao ``versionGroup`` de cada um; ``null`` = igual ao atual);
    - ``versionGroups`` e ``methods``: os nomes por índice;
    - ``learnsets``: por id de pokémon e índice do grupo de versões, a lista
      plana ``[golpe, modo, nível, golpe, modo, nível...]``;
    - ``machines``: por grupo de versões, o item da TM de cada golpe
      (``"tm71"``, ``"hm01"``, ``"tr12"``).

    Falha com modo de aprender desconhecido."""
    learns = list(
        PokemonMoveLearn.objects.values_list(
            "pokemon__pokeapi_id", "version_group__name", "move_id", "method", "level"
        ).order_by(
            "pokemon__pokeapi_id",
            "version_group__order",
            "method",
            "level",
            "order",
            "move__name",
        )
    )
    if unknown := sorted({row[3] for row in learns} - set(MOVE_LEARN_METHODS)):
        raise CatalogError(f"modos de aprender golpes desconhecidos: {unknown}")
    moves = list(
        Move.objects.filter(id__in={row[2] for row in learns}).order_by("name")
    )
    move_index = {m.id: i for i, m in enumerate(moves)}
    groups = list(
        VersionGroup.objects.filter(name__in={row[1] for row in learns}).values_list(
            "name", flat=True
        )
    )
    group_index = {name: i for i, name in enumerate(groups)}
    method_index = {name: i for i, name in enumerate(MOVE_LEARN_METHODS)}

    learnsets: dict[str, dict[str, list[int]]] = {}
    for pokemon, group, move, method, level in learns:
        flat = learnsets.setdefault(str(pokemon), {}).setdefault(
            str(group_index[group]), []
        )
        flat += [move_index[move], method_index[method], level]

    machines: dict[str, dict[str, str]] = {}
    for move, group, item in MoveMachine.objects.filter(
        move_id__in=move_index, version_group__name__in=group_index
    ).values_list("move_id", "version_group__name", "item"):
        machines.setdefault(group, {})[str(move_index[move])] = item

    def move_json(m: Move) -> dict:
        return {
            "name": m.name,
            "label": m.label or m.name,
            "type": m.type,
            "category": m.damage_class,
            "power": m.power,
            "accuracy": m.accuracy,
            "pp": m.pp,
            "priority": m.priority,
            "target": m.target,
            "effect": m.effect,
            **(
                {
                    "past": [
                        {
                            "versionGroup": v["version_group"],
                            "power": v["power"],
                            "accuracy": v["accuracy"],
                            "pp": v["pp"],
                            "type": v["type"],
                        }
                        for v in m.past_values
                    ]
                }
                if m.past_values
                else {}
            ),
        }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "version": version,
        "moves": [move_json(m) for m in moves],
        "versionGroups": groups,
        "methods": list(MOVE_LEARN_METHODS),
        "learnsets": learnsets,
        "machines": {g: machines[g] for g in groups if g in machines},
    }


def build_catalog(version: str) -> dict:
    groups, versions = _versions()
    pokedexes, species_of_group = _pokedexes()
    methods = _shiny_methods()
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
        # Para as espécies com forma regional, as formas presentes em cada
        # jogo; e as formas que não podem ser shiny em cada versão.
        "gameForms": _game_forms(species_of_group),
        "gameShinyLocks": _game_shiny_locks(species_of_group),
        # Formas que podem aparecer como alfa em cada jogo (Legends: Arceus e
        # Legends: Z-A), para o motivo "Sem alfa". Chave nova, aditiva.
        "alphaForms": _alpha_forms(species_of_group),
        # Espécies que o jogo aceita pelo HOME, fora das pokédex, e que só se
        # caçam por ovo (o Phione no Scarlet/Violet). Chave nova, aditiva.
        "homeEggs": _home_eggs(species_of_group),
        # Evoluções entre formas das famílias com forma regional (#121):
        # pares [de, para] e as formas que não evoluem. Chave nova, aditiva.
        "formEvolutions": _form_evolutions(),
        # Como cada forma evolui (#133): os métodos da PokéAPI por par de
        # formas e jogo, com o padrão, os nomes em inglês dos itens, golpes e
        # lugares, e a frase e o link "Veja mais" nos casos bizarros. Chave
        # nova, aditiva.
        "evolutionMethods": _evolution_methods(),
        # Os golpes ficam num arquivo à parte (``build_moves``), baixado só
        # ao abrir a aba Golpes ou a busca (#134); aqui, só o nome dele.
        # Chave nova, aditiva.
        "movesFile": moves_file_name(version),
        # Métodos de shiny hunt e os jogos onde existem (a primeira unidade
        # é a padrão). Chave nova, aditiva: o schemaVersion continua.
        "shinyMethods": methods,
        # Odds de shiny por método e jogo (sorteios, chance ou DexNav), com
        # o Charm, as cadeias e os modificadores. Chave nova, aditiva.
        "shinyOdds": _shiny_odds(methods),
    }
