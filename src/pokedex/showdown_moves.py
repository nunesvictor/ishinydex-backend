"""Golpes por forma dos jogos que a PokéAPI não tem (#142), do Showdown.

A PokéAPI não tem os golpes do Legends: Z-A (pokeapi#1332). O Showdown tem,
no mod ``gen9legends`` (``pokedex.showdown.read_learnsets``). O arquivo
``SHOWDOWN_LEARNSETS_FILE`` dá o mod de cada grupo de versões e as formas
que o Showdown chama diferente da PokéAPI.

Cada forma do Showdown vira um pokémon da PokéAPI pelo nome sem
pontuação (``floetteeternal`` → ``floette-eternal``) ou, sem par, pela
espécie (``keldeo`` → ``keldeo-ordinary``, o padrão dela). As formas da
espécie que o Showdown não lista (``pumpkaboo-large``) aprendem os golpes da
forma padrão, como no Showdown, se tiverem os mesmos tipos e não forem mega
nem só de batalha.

Os códigos viram o modo de aprender: ``9L12`` é ``level-up`` no nível 12,
``9M`` é ``machine`` (sem o número da TM, que o Showdown não tem) e ``8R``,
o golpe que a forma do Rotom ganha ao trocar, é ``form-change``. Os de evento
(``9S0``) ficam de fora. Falha com forma, golpe ou código sem par.

Rodar depois do ``sync_pokeapi``, que apaga os golpes dos pokémon que importa.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path

from django.db import transaction

from pokedex.models import Move, Pokemon, PokemonMoveLearn, VersionGroup
from pokedex.showdown import ShowdownError, read_learnsets

SHOWDOWN_LEARNSETS_FILE = (
    Path(__file__).resolve().parent / "data/showdown_learnsets.json"
)

_CODE = re.compile(r"\d+([LMRS])(\d*)")
_METHODS = {"L": "level-up", "M": "machine", "R": "form-change"}


class ShowdownMovesError(ValueError):
    pass


def showdown_id(name: str) -> str:
    """O id do Showdown para um nome da PokéAPI: ``"floette-eternal"`` →
    ``"floetteeternal"``."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def learn_method(code: str) -> tuple[str, int] | None:
    """O modo e o nível de um código do Showdown; ``None`` para os de evento."""
    match = _CODE.fullmatch(code)
    if not match:
        raise ShowdownMovesError(f"código de golpe do Showdown desconhecido: {code}")
    letter, level = match.groups()
    if letter == "S":
        return None
    return _METHODS[letter], int(level or 0)


class ShowdownMovesImporter:
    def __init__(self, root: Path | str, log: Callable[[str], None] = print):
        self.root = root
        self.log = log

    @transaction.atomic
    def run(self) -> int:
        data = json.loads(SHOWDOWN_LEARNSETS_FILE.read_text(encoding="utf-8"))
        aliases: dict[str, str] = data["aliases"]
        groups = dict(
            VersionGroup.objects.filter(name__in=data["versionGroups"]).values_list(
                "name", "id"
            )
        )
        moves = {
            showdown_id(name): id for name, id in Move.objects.values_list("name", "id")
        }
        pokemon = list(
            Pokemon.objects.select_related("species").prefetch_related("types", "forms")
        )
        by_name = {p.name: p for p in pokemon}
        by_id = {showdown_id(p.name): p for p in pokemon}
        default_of = {
            showdown_id(p.species.name): p
            for p in pokemon
            if p.species and p.is_default
        }

        def resolve(key: str) -> Pokemon:
            found = by_name.get(aliases[key]) if key in aliases else None
            found = found or by_id.get(key) or default_of.get(key)
            if found is None:
                raise ShowdownMovesError(f"forma do Showdown sem par na PokéAPI: {key}")
            return found

        def types(p: Pokemon) -> list[str]:
            return [t.type for t in sorted(p.types.all(), key=lambda t: t.slot)]

        def same_moves_as_default(p: Pokemon, default: Pokemon) -> bool:
            form = next((f for f in p.forms.all() if f.is_default), None)
            return (
                form is not None
                and not form.is_mega
                and not form.is_battle_only
                and types(p) == types(default)
            )

        rows: list[PokemonMoveLearn] = []
        for group, mod in data["versionGroups"].items():
            if group not in groups:
                continue
            try:
                learnsets = read_learnsets(self.root, mod)
            except ShowdownError as error:
                raise ShowdownMovesError(str(error)) from None
            learns: dict[int, list[tuple[int, str, int]]] = {}
            for key, learnset in learnsets.items():
                entries = []
                for move, codes in learnset.items():
                    if move not in moves:
                        raise ShowdownMovesError(
                            f"golpe do Showdown sem par na PokéAPI: {move}"
                        )
                    for code in codes:
                        if method := learn_method(code):
                            entries.append((moves[move], *method))
                learns[resolve(key).id] = list(dict.fromkeys(entries))
            for p in pokemon:
                default = (
                    default_of.get(showdown_id(p.species.name)) if p.species else None
                )
                if (
                    p.id not in learns
                    and default is not None
                    and default.id in learns
                    and same_moves_as_default(p, default)
                ):
                    learns[p.id] = learns[default.id]
            rows += [
                PokemonMoveLearn(
                    pokemon_id=p,
                    move_id=move,
                    version_group_id=groups[group],
                    method=method,
                    level=level,
                )
                for p, entries in learns.items()
                for move, method, level in entries
            ]

        PokemonMoveLearn.objects.filter(version_group_id__in=groups.values()).delete()
        PokemonMoveLearn.objects.bulk_create(rows, batch_size=5000)
        self.log(f"  {PokemonMoveLearn._meta.verbose_name_plural}: {len(rows)}")
        return len(rows)
