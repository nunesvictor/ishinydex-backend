"""Os itens do Pokémon Showdown (smogon/pokemon-showdown, MIT) por jogo (#138).

A PokéAPI não diz em que jogo um item segurável funciona: o atributo
``holdable`` falta nos itens da 9ª geração e sobra na Potion, e as Mega Stones
aparecem na 8ª e na 9ª. O Showdown mantém isso por geração e por jogo
(``data/items.ts`` e os ``data/mods/<mod>/items.ts``), e é o formato para onde
o team builder exporta.

Os arquivos são TypeScript com funções dentro: são lidos **como texto**, sem
executar nada. De cada item saem só os campos simples (``name``, ``gen``,
``isNonstandard``, ``isPokeball`` e o ``inherit`` dos mods). Um mod herda do
``inherit`` do ``scripts.ts`` dele; sem ele, ``genN`` herda de ``genN+1`` e o
``gen8`` herda da base (a geração atual, ``gen9``).
"""

import json
import re
from pathlib import Path

BASE = "base"
BASE_GEN = 9

_ENTRY = re.compile(r"^\t([a-z0-9]+): \{\n(.*?)^\t\},?$", re.S | re.M)
_FIELD = re.compile(
    r"^\t\t(name|gen|isNonstandard|isPokeball|inherit): ([^,\n]+),", re.M
)
_GEN = re.compile(r"^\tgen: (\d+),", re.M)
_INHERIT = re.compile(r"^\tinherit: '([a-z0-9]+)',", re.M)


class ShowdownError(ValueError):
    pass


def parse_items(text: str) -> dict[str, dict]:
    """``{id: {campo: valor}}`` de um ``items.ts``, só com os campos simples."""
    return {
        key: {field: json.loads(value) for field, value in _FIELD.findall(body)}
        for key, body in _ENTRY.findall(text)
    }


class ShowdownItems:
    """Os itens de cada mod de um clone de ``data/`` do Showdown."""

    def __init__(self, root: Path | str):
        self.data = Path(root) / "data"
        if not (self.data / "items.ts").exists():
            raise ShowdownError(f"Showdown: data/items.ts não existe em {root}")
        self._tables: dict[str, dict[str, dict]] = {}

    def _mod(self, mod: str) -> tuple[int, str]:
        """A geração do mod e o mod de que ele herda."""
        folder = self.data / "mods" / mod
        if not folder.is_dir():
            raise ShowdownError(f"mod do Showdown desconhecido: {mod}")
        scripts = folder / "scripts.ts"
        text = scripts.read_text(encoding="utf-8") if scripts.exists() else ""
        gen_match = _GEN.search(text)
        inherit = _INHERIT.search(text)
        number = re.fullmatch(r"gen(\d)", mod)
        if gen_match:
            gen = int(gen_match.group(1))
        elif number:
            gen = int(number.group(1))
        elif inherit:
            # gen4pt: só ``inherit: 'gen4'``, com a geração do pai.
            gen = self._mod(inherit.group(1))[0]
        else:
            raise ShowdownError(f"mod do Showdown sem geração: {mod}")
        if inherit:
            return gen, inherit.group(1)
        return gen, BASE if gen >= BASE_GEN - 1 else f"gen{gen + 1}"

    def _table(self, mod: str) -> dict[str, dict]:
        if mod not in self._tables:
            if mod == BASE:
                table = parse_items((self.data / "items.ts").read_text("utf-8"))
            else:
                parent = self._table(self._mod(mod)[1])
                file = self.data / "mods" / mod / "items.ts"
                own = parse_items(file.read_text("utf-8")) if file.exists() else {}
                table = dict(parent)
                for key, item in own.items():
                    table[key] = (
                        {**parent.get(key, {}), **item} if item.get("inherit") else item
                    )
            self._tables[mod] = table
        return self._tables[mod]

    def held_items(self, mod: str) -> dict[str, str]:
        """``{id: nome}`` dos itens que existem no mod: da geração dele ou
        anterior, sem ``isNonstandard`` (``"Past"``, ``"Unobtainable"``...) e
        sem as pokébolas, que ninguém segura para batalhar."""
        gen = BASE_GEN if mod == BASE else self._mod(mod)[0]
        items = {
            key: item["name"]
            for key, item in self._table(mod).items()
            if "name" in item
            and item.get("gen", 0) <= gen
            and not item.get("isNonstandard")
            and not item.get("isPokeball")
        }
        if not items:
            raise ShowdownError(f"nenhum item no mod do Showdown {mod}")
        return items
