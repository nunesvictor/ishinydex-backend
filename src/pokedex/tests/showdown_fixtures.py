"""Um clone mínimo de ``data/`` do Showdown, num diretório temporário."""

import tempfile
from pathlib import Path

# O cabeçalho dos mods, como no Showdown.
MOD = "export const Items: import('../../../sim/dex-items').ModdedItemDataTable = {\n"

ITEMS = """export const Items: import('../sim/dex-items').ItemDataTable = {
\tabilityshield: {
\t\tname: "Ability Shield",
\t\tspritenum: 746,
\t\tfling: {
\t\t\tbasePower: 30,
\t\t},
\t\tonSetAbility(ability, target, source, effect) {
\t\t\treturn null;
\t\t},
\t\tnum: 1881,
\t\tgen: 9,
\t},
\tleftovers: {
\t\tname: "Leftovers",
\t\tnum: 234,
\t\tgen: 2,
\t},
\tkingsrock: {
\t\tname: "King's Rock",
\t\tnum: 221,
\t\tgen: 2,
\t},
\tfiriumz: {
\t\tname: "Firium Z",
\t\tnum: 777,
\t\tgen: 7,
\t\tisNonstandard: "Past",
\t},
\tleek: {
\t\tname: "Leek",
\t\tnum: 259,
\t\tgen: 8,
\t},
\tberserkgene: {
\t\tname: "Berserk Gene",
\t\tnum: 0,
\t\tgen: 2,
\t\tisNonstandard: "Past",
\t},
\tpokeball: {
\t\tname: "Poke Ball",
\t\tnum: 4,
\t\tgen: 1,
\t\tisPokeball: true,
\t},
};
"""

GEN8_ITEMS = MOD + """\tfiriumz: {
\t\tinherit: true,
\t\tisNonstandard: null,
\t},
};
"""

GEN2_ITEMS = MOD + """\tberserkgene: {
\t\tinherit: true,
\t\tisNonstandard: null,
\t},
\tleek: {
\t\tname: "Leek",
\t\tnum: 259,
\t\tgen: 2,
\t},
};
"""

BDSP_ITEMS = MOD + """\tkingsrock: {
\t\tinherit: true,
\t\tisNonstandard: "Past",
\t},
};
"""


def showdown_tree(**extra: str) -> tempfile.TemporaryDirectory:
    """O clone mínimo: a base (9ª geração), os mods ``gen8``, ``gen2``,
    ``gen8bdsp`` (com ``gen`` e ``inherit``), ``gen4pt`` (só ``inherit``) e
    ``gen1``, que não tem item. ``extra``: ``{"mods/x/items.ts": texto}``."""
    tmp = tempfile.TemporaryDirectory()
    data = Path(tmp.name) / "data"
    files = {
        "items.ts": ITEMS,
        "mods/gen8/items.ts": GEN8_ITEMS,
        "mods/gen8/scripts.ts": "export const Scripts = {\n\tgen: 8,\n};\n",
        "mods/gen2/items.ts": GEN2_ITEMS,
        "mods/gen8bdsp/items.ts": BDSP_ITEMS,
        "mods/gen8bdsp/scripts.ts": (
            "export const Scripts = {\n\tgen: 8,\n\tinherit: 'gen8',\n};\n"
        ),
        "mods/gen4pt/scripts.ts": "export const Scripts = {\n\tinherit: 'gen4',\n};\n",
        "mods/gen1/scripts.ts": "export const Scripts = {\n\tinherit: 'gen2',\n};\n",
        **extra,
    }
    for name in ("gen3", "gen4", "gen5", "gen6", "gen7"):
        (data / "mods" / name).mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp
