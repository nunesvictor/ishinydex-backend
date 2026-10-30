"""Um "mundo" pequeno da PokéAPI para testar o importador sem rede.

Os dicts seguem o formato real da API (só com os campos usados). A ordem da
lista de espécies põe o Pikachu antes do Pichu, de quem ele evolui — o mesmo
cenário que deixava ``evolves_from_species`` vazio no import antigo.
"""

import copy

from core.services.pokeapi import resource_path

BASE = "https://pokeapi.co/api/v2"


def ref(endpoint: str, name: str, id_: int) -> dict:
    return {"name": name, "url": f"{BASE}/{endpoint}/{id_}/"}


VERSION_GROUPS = {
    "red-blue": (1, "generation-i", 1, ["red", "blue"]),
    "gold-silver": (3, "generation-ii", 3, ["gold"]),
    "sword-shield": (20, "generation-viii", 20, ["sword"]),
    # Nenhuma forma nem versão importada a referencia.
    "brilliant-diamond-shining-pearl": (23, "generation-viii", 23, []),
}
VERSIONS = {
    "red": (1, "red-blue"),
    "blue": (2, "red-blue"),
    "gold": (4, "gold-silver"),
    # Sem game_indices em nenhum pokémon (como os jogos recentes).
    "sword": (33, "sword-shield"),
}
SPECIES_IDS = {"pikachu": 25, "raichu": 26, "pichu": 172}


def _version_group(name):
    id_, generation, order, versions = VERSION_GROUPS[name]
    return {
        "id": id_,
        "name": name,
        "order": order,
        "generation": ref("generation", generation, order),
        "pokedexes": [ref("pokedex", "kanto", 2)],
        "regions": [ref("region", "kanto", 1)],
        "versions": [ref("version", v, VERSIONS[v][0]) for v in versions],
    }


def _version(name):
    id_, group = VERSIONS[name]
    return {
        "id": id_,
        "name": name,
        "version_group": ref("version-group", group, VERSION_GROUPS[group][0]),
    }


def _species(name, *, evolves_from=None, varieties, is_baby=False):
    id_ = SPECIES_IDS[name]
    return {
        "id": id_,
        "name": name,
        "order": id_,
        "gender_rate": 4,
        "capture_rate": 190,
        "base_happiness": 50,
        "is_baby": is_baby,
        "is_legendary": False,
        "is_mythical": False,
        "hatch_counter": 10,
        "has_gender_differences": name == "pikachu",
        "forms_switchable": False,
        "growth_rate": ref("growth-rate", "medium", 2),
        "egg_groups": [ref("egg-group", "ground", 5), ref("egg-group", "fairy", 6)],
        "color": ref("pokemon-color", "yellow", 10),
        "shape": ref("pokemon-shape", "quadruped", 8),
        "generation": ref("generation", "generation-i", 1),
        "evolution_chain": {"url": f"{BASE}/evolution-chain/10/"},
        "evolves_from_species": (
            ref("pokemon-species", evolves_from, SPECIES_IDS[evolves_from])
            if evolves_from
            else None
        ),
        "pokedex_numbers": [
            {"entry_number": id_, "pokedex": ref("pokedex", "national", 1)},
        ],
        "varieties": [
            {"is_default": is_default, "pokemon": ref("pokemon", pokemon, pid)}
            for pokemon, pid, is_default in varieties
        ],
    }


def _pokemon(name, id_, species, *, forms, types, abilities, stats, games, **extra):
    return {
        "id": id_,
        "name": name,
        "order": id_,
        "base_experience": 112,
        "height": 4,
        "weight": 60,
        "is_default": extra.get("is_default", True),
        "species": ref("pokemon-species", species, SPECIES_IDS[species]),
        "sprites": {
            "front_default": f"https://img/{id_}.png",
            "other": {"official-artwork": {"front_default": f"https://art/{id_}.png"}},
        },
        "cries": {"latest": f"https://cries/{id_}.ogg"},
        "forms": [ref("pokemon-form", f, fid) for f, fid in forms],
        "types": [
            {"slot": slot, "type": ref("type", t, 13)}
            for slot, t in enumerate(types, start=1)
        ],
        "abilities": [
            {"slot": slot, "is_hidden": hidden, "ability": ref("ability", a, 9)}
            for a, slot, hidden in abilities
        ],
        "stats": [
            {"stat": ref("stat", s, 1), "effort": effort, "base_stat": base}
            for s, base, effort in stats
        ],
        "game_indices": [
            {"game_index": index, "version": ref("version", v, VERSIONS[v][0])}
            for v, index in games
        ],
        "moves": [
            {
                "move": ref("move", "thunder-shock", 84),
                "version_group_details": [
                    {
                        "level_learned_at": level,
                        "move_learn_method": ref("move-learn-method", method, 1),
                        "version_group": ref(
                            "version-group", group, VERSION_GROUPS[group][0]
                        ),
                        "order": None,
                    }
                    for group, method, level in extra.get(
                        "learns", [("red-blue", "level-up", 1)]
                    )
                ],
            }
        ],
    }


def _form(name, id_, pokemon, pokemon_id, group, *, is_default=True, form_name=""):
    return {
        "id": id_,
        "name": name,
        "order": id_,
        "form_order": 1 if is_default else 2,
        "is_default": is_default,
        "is_battle_only": False,
        "is_mega": False,
        "form_name": form_name,
        "pokemon": ref("pokemon", pokemon, pokemon_id),
        "sprites": {"front_default": f"https://img/form-{id_}.png"},
        "types": [{"slot": 1, "type": ref("type", "electric", 13)}],
        "version_group": ref("version-group", group, VERSION_GROUPS[group][0]),
    }


def _detail(trigger, group, **conditions):
    """Um ``evolution_details`` com todos os campos da API (os vazios como
    ela os traz: ``null``, ``false`` e ``""``)."""
    detail = {
        "gender": None,
        "held_item": None,
        "item": None,
        "known_move": None,
        "known_move_type": None,
        "location": None,
        "min_affection": None,
        "min_beauty": None,
        "min_happiness": None,
        "min_level": None,
        "needs_overworld_rain": False,
        "party_species": None,
        "party_type": None,
        "relative_physical_stats": None,
        "time_of_day": "",
        "trade_species": None,
        "turn_upside_down": False,
        "allowed_natures": [],
        "condition_expression": None,
        "region": None,
        "required_pokemon_form": None,
        "evolved_pokemon_form": None,
        "is_default": False,
        "trigger": ref("evolution-trigger", trigger, 1),
        "version_group": ref("version-group", group, VERSION_GROUPS[group][0]),
    }
    return detail | conditions


def _evolution_chain():
    """Pichu → Pikachu → Raichu, com dois métodos na segunda ligação."""
    return {
        "id": 10,
        "baby_trigger_item": None,
        "chain": {
            "species": ref("pokemon-species", "pichu", 172),
            "evolution_details": [],
            "evolves_to": [
                {
                    "species": ref("pokemon-species", "pikachu", 25),
                    "evolution_details": [
                        _detail(
                            "level-up",
                            "gold-silver",
                            min_happiness=220,
                            # O 0 vale: Ataque igual à Defesa.
                            relative_physical_stats=0,
                            is_default=True,
                        )
                    ],
                    "evolves_to": [
                        {
                            "species": ref("pokemon-species", "raichu", 26),
                            "evolution_details": [
                                _detail(
                                    "use-item",
                                    "red-blue",
                                    item=ref("item", "thunder-stone", 83),
                                    required_pokemon_form=ref(
                                        "pokemon-form", "pikachu", 25
                                    ),
                                    is_default=True,
                                ),
                                _detail(
                                    "level-up",
                                    "sword-shield",
                                    location=ref("location", "viridian-forest", 88),
                                    allowed_natures=[
                                        ref("nature", "hardy", 1),
                                        ref("nature", "docile", 7),
                                    ],
                                    condition_expression={
                                        "expression": "EC 100 % 0 ==",
                                        "percentage_chance": 1.0,
                                        "variables": [],
                                    },
                                ),
                            ],
                            "evolves_to": [],
                        }
                    ],
                }
            ],
        },
    }


def _move():
    """O Thunder Shock, com a TM do Red/Blue e um valor antigo."""
    return {
        "id": 84,
        "name": "thunder-shock",
        "accuracy": 100,
        "effect_chance": 10,
        "pp": 30,
        "priority": 0,
        "power": 40,
        "damage_class": ref("move-damage-class", "special", 3),
        "generation": ref("generation", "generation-i", 1),
        "target": ref("move-target", "selected-pokemon", 10),
        "type": ref("type", "electric", 13),
        "names": [{"language": ref("language", "en", 9), "name": "Thunder Shock"}],
        "effect_entries": [
            {
                "language": ref("language", "en", 9),
                "short_effect": "Has a $effect_chance% chance to paralyze.",
            }
        ],
        "past_values": [
            {
                "accuracy": None,
                "power": 35,
                "pp": None,
                "effect_chance": None,
                "effect_entries": [],
                "type": None,
                "version_group": ref("version-group", "gold-silver", 3),
            }
        ],
        "machines": [
            {
                "machine": ref("machine", "", 400),
                "version_group": ref("version-group", "red-blue", 1),
            }
        ],
        "learned_by_pokemon": [],
    }


def _named(id_, name, english, **extra):
    """Item ou lugar: só o nome em cada idioma importa."""
    return {
        "id": id_,
        "name": name,
        "names": [
            {"language": ref("language", "ja", 1), "name": english.upper()},
            {"language": ref("language", "en", 9), "name": english},
        ],
        **extra,
    }


def build_world() -> dict[str, dict]:
    """Recursos por caminho (``endpoint/id``), como o cliente os entrega."""
    resources = [
        _species(
            "pikachu",
            evolves_from="pichu",
            varieties=[("pikachu", 25, True), ("pikachu-gmax", 10199, False)],
        ),
        _species("raichu", evolves_from="pikachu", varieties=[("raichu", 26, True)]),
        _species("pichu", varieties=[("pichu", 172, True)], is_baby=True),
        _pokemon(
            "pikachu",
            25,
            "pikachu",
            forms=[("pikachu", 25)],
            types=["electric"],
            abilities=[("static", 1, False), ("lightning-rod", 3, True)],
            stats=[("hp", 35, 0), ("speed", 90, 2)],
            games=[("red", 84), ("blue", 84), ("gold", 156)],
            learns=[
                ("red-blue", "level-up", 1),
                ("red-blue", "machine", 0),
                ("sword-shield", "level-up", 1),
            ],
        ),
        _pokemon(
            "pikachu-gmax",
            10199,
            "pikachu",
            forms=[("pikachu-gmax", 10423)],
            types=["electric"],
            abilities=[("static", 1, False)],
            stats=[("hp", 35, 0)],
            games=[],
            is_default=False,
        ),
        _pokemon(
            "raichu",
            26,
            "raichu",
            forms=[("raichu", 26)],
            types=["electric"],
            abilities=[("static", 1, False)],
            stats=[("hp", 60, 0), ("speed", 110, 3)],
            games=[("red", 85)],
        ),
        _pokemon(
            "pichu",
            172,
            "pichu",
            forms=[("pichu", 172), ("pichu-spiky-eared", 10077)],
            types=["electric"],
            abilities=[("static", 1, False)],
            stats=[("hp", 20, 0)],
            games=[("gold", 172)],
        ),
        _form("pikachu", 25, "pikachu", 25, "red-blue"),
        _form("pikachu-gmax", 10423, "pikachu-gmax", 10199, "sword-shield"),
        _form("raichu", 26, "raichu", 26, "red-blue"),
        _form("pichu", 172, "pichu", 172, "gold-silver"),
        _form(
            "pichu-spiky-eared",
            10077,
            "pichu",
            172,
            "gold-silver",
            is_default=False,
            form_name="spiky-eared",
        ),
        _evolution_chain(),
        _move(),
        {
            "id": 400,
            "item": ref("item", "tm24", 328),
            "move": ref("move", "thunder-shock", 84),
            "version_group": ref("version-group", "red-blue", 1),
        },
        _named(83, "thunder-stone", "Thunder Stone", cost=3000),
        _named(88, "viridian-forest", "Viridian Forest", areas=[]),
        *(_version(v) for v in VERSIONS),
        *(_version_group(vg) for vg in VERSION_GROUPS),
    ]

    world = {}
    endpoints = {
        "pokemon-species": [r for r in resources if "varieties" in r],
        "pokemon": [r for r in resources if "game_indices" in r],
        "pokemon-form": [r for r in resources if "form_order" in r],
        "version": [
            r
            for r in resources
            if "version_group" in r and "form_order" not in r and "move" not in r
        ],
        "version-group": [r for r in resources if "pokedexes" in r],
        "evolution-chain": [r for r in resources if "chain" in r],
        "item": [r for r in resources if "cost" in r],
        "location": [r for r in resources if "areas" in r],
        "move": [r for r in resources if "learned_by_pokemon" in r],
        "machine": [r for r in resources if "move" in r and "item" in r],
    }

    for endpoint, items in endpoints.items():
        for item in items:
            world[f"{endpoint}/{item['id']}"] = item

    world["version/_list"] = {
        "results": [ref("version", name, v[0]) for name, v in VERSIONS.items()]
    }
    world["version-group/_list"] = {
        "results": [
            ref("version-group", name, vg[0]) for name, vg in VERSION_GROUPS.items()
        ]
    }
    world["pokemon-species/_list"] = {
        "results": [
            ref("pokemon-species", name, id_) for name, id_ in SPECIES_IDS.items()
        ]
    }

    return world


class FakePokeAPIClient:
    """Mesma interface do PokeAPIClient usada pelo importador, sem rede."""

    def __init__(self, world: dict[str, dict] | None = None):
        self.world = world if world is not None else build_world()
        self.requested: list[str] = []

    def list(self, endpoint):
        return self.world[f"{endpoint}/_list"]["results"]

    def get(self, url_or_path):
        path = resource_path(url_or_path)
        self.requested.append(path)
        return copy.deepcopy(self.world[path])

    def get_many(self, urls_or_paths):
        paths = list(dict.fromkeys(resource_path(u) for u in urls_or_paths))
        return {path: self.get(path) for path in paths}

    def resource(self, endpoint: str, name: str) -> dict:
        """Recurso do mundo pelo nome (para alterar em testes de atualização)."""
        return next(
            r
            for path, r in self.world.items()
            if path.startswith(f"{endpoint}/")
            and not path.endswith("_list")
            and r["name"] == name
        )
