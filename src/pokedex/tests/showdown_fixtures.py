"""Um clone mínimo de ``data/`` do Showdown, num diretório temporário.

Os textos são escritos aqui, no formato dos arquivos do Showdown, sem copiar
o código deles: só os campos que o leitor usa, mais um objeto e uma função
inventados, que o leitor tem de ignorar."""

import tempfile
from pathlib import Path

# O cabeçalho dos mods, como no Showdown.
MOD = "export const Items: import('../../../sim/dex-items').ModdedItemDataTable = {\n"

ITEMS = """export const Items: import('../sim/dex-items').ItemDataTable = {
\tabilityshield: {
\t\tname: "Ability Shield",
\t\textra: {
\t\t\tvalue: 1,
\t\t},
\t\tonAnything() {
\t\t\treturn 1;
\t\t},
\t\tgen: 9,
\t},
\tleftovers: {
\t\tname: "Leftovers",
\t\tgen: 2,
\t},
\tkingsrock: {
\t\tname: "King's Rock",
\t\tgen: 2,
\t},
\tfiriumz: {
\t\tname: "Firium Z",
\t\tgen: 7,
\t\tisNonstandard: "Past",
\t},
\tleek: {
\t\tname: "Leek",
\t\tgen: 8,
\t},
\tberserkgene: {
\t\tname: "Berserk Gene",
\t\tgen: 2,
\t\tisNonstandard: "Past",
\t},
\tpokeball: {
\t\tname: "Poke Ball",
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


# Um learnsets.ts de mod, com as formas e golpes que o importador usa: a forma
# com ``inherit``, os códigos de nível, TM, troca de forma e evento, e uma
# forma só com ``eventData``, sem ``learnset``.
LEARNSETS = (
    (
        "export const Learnsets: "
        "import('../../../sim/dex-species').ModdedLearnsetDataTable = {\n"
    )
    + """\tpumpkaboo: {
\t\tlearnset: {
\t\t\tastonish: ["9L1"],
\t\t\tshadowball: ["9M", "9L30"],
\t\t},
\t},
\tfloette: {
\t\tlearnset: {
\t\t\ttackle: ["9L1"],
\t\t},
\t},
\tfloetteeternal: {
\t\tinherit: true,
\t\tlearnset: {
\t\t\tlightofruin: ["9L50", "9S0"],
\t\t},
\t},
\tmeowsticf: {
\t\tlearnset: {
\t\t\tshadowball: ["9M"],
\t\t},
\t},
\trotomwash: {
\t\tlearnset: {
\t\t\thydropump: ["8R"],
\t\t\tshadowball: ["9M"],
\t\t},
\t},
\tmewtwo: {
\t\teventData: [
\t\t\t{generation: 9, level: 70},
\t\t],
\t},
};
"""
)
