"""Marca de origem (origin mark) do espécime, como no Pokémon HOME.

A marca identifica o jogo em que o Pokémon foi obtido pela primeira vez. Jogos
que interagem entre si compartilham a marca, e as DLCs usam a do jogo base.
Gen 3–5, Colosseum/XD e Champions não têm marca, com uma exceção: FireRed e
LeafGreen do Switch (HOME 4.1.0) levam a marca do Game Boy Advance. O
catálogo não separa as duas edições, então todo OT de FRLG fica com ela.
Pokémon GO não é uma versão da PokéAPI: a marca vem de ``Specimen.is_from_go``
e tem prioridade.

Referência: https://bulbapedia.bulbagarden.net/wiki/Origin_mark
"""

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

GO = "go"
NONE = "none"

# Marca → grupos de versão (``VersionGroup.name``), na ordem de lançamento.
ORIGIN_MARK_VERSION_GROUPS: dict[str, tuple[str, ...]] = {
    "game-boy": (
        "red-green-japan",
        "blue-japan",
        "red-blue",
        "yellow",
        "gold-silver",
        "crystal",
    ),
    "gba": ("firered-leafgreen",),
    "kalos": ("x-y", "omega-ruby-alpha-sapphire"),
    "alola": ("sun-moon", "ultra-sun-ultra-moon"),
    "lets-go": ("lets-go-pikachu-lets-go-eevee",),
    "galar": ("sword-shield", "the-isle-of-armor", "the-crown-tundra"),
    "bdsp": ("brilliant-diamond-shining-pearl",),
    "hisui": ("legends-arceus",),
    "paldea": ("scarlet-violet", "the-teal-mask", "the-indigo-disk"),
    "lumiose": ("legends-za", "mega-dimension"),
}

# Siglas dos jogos, como os jogadores conhecem; não precisam de tradução.
# Só "sem marca" é texto e passa pelo gettext.
ORIGIN_MARK_LABELS = {
    "game-boy": "GB",
    "gba": "GBA",
    "kalos": "XY/ORAS",
    "alola": "SM/USUM",
    "lets-go": "LGPE",
    "galar": "SwSh",
    "bdsp": "BDSP",
    "hisui": "PLA",
    "paldea": "SV",
    "lumiose": "PLZA",
    GO: "GO",
    NONE: _("No origin mark"),
}

_MARK_BY_VERSION_GROUP = {
    group: mark
    for mark, groups in ORIGIN_MARK_VERSION_GROUPS.items()
    for group in groups
}
MARKED_VERSION_GROUPS = tuple(_MARK_BY_VERSION_GROUP)


def origin_mark_for(version_group: str | None, is_from_go: bool) -> str | None:
    """Slug da marca, ou ``None`` se o espécime não tiver marca."""
    if is_from_go:
        return GO

    return _MARK_BY_VERSION_GROUP.get(version_group or "")


def origin_mark_q(mark: str) -> Q:
    """Condição de ``Specimen`` para uma marca (``none``: sem marca); slug
    desconhecido → nenhum resultado."""
    if mark == GO:
        return Q(is_from_go=True)

    if mark == NONE:
        return Q(is_from_go=False) & ~Q(
            origin_version__version_group__name__in=MARKED_VERSION_GROUPS
        )

    groups = ORIGIN_MARK_VERSION_GROUPS.get(mark)
    if groups is None:
        return Q(pk__in=[])

    return Q(is_from_go=False, origin_version__version_group__name__in=groups)


def origin_mark_options() -> list[dict]:
    """Choices de ``/specimens/options/``: marcas em ordem, GO e "sem marca"."""
    return [
        {"value": mark, "label": str(label)}
        for mark, label in ORIGIN_MARK_LABELS.items()
    ]
