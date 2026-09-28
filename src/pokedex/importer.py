"""Importação da PokéAPI em duas fases.

1. **Busca**: parte das espécies e segue as referências (variedades → pokémon →
   formas → versões → grupos de versão), baixando cada nível em paralelo.
2. **Gravação**: numa transação, em ordem de dependência, com upsert em lote
   por ``name`` e mapas ``nome → id`` em memória. As relações que dependem de
   registros criados depois (``evolves_from_species``, variedades) são
   resolvidas numa segunda passada, então a ordem da API não importa.

É idempotente: rodar de novo atualiza os campos e as relações, sem duplicar.
Golpes (moves) não são importados.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from django.db import models, transaction

from core.services.pokeapi import PokeAPIClient
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
    Version,
    VersionGameIndex,
    VersionGroup,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


class UnknownSpeciesError(ValueError):
    pass


def _name(ref: dict | None) -> str | None:
    return ref["name"] if ref else None


def _names(refs: Iterable[dict]) -> list[str]:
    return [ref["name"] for ref in refs]


@dataclass
class FetchedData:
    species: list[dict] = field(default_factory=list)
    pokemon: list[dict] = field(default_factory=list)
    forms: list[dict] = field(default_factory=list)
    versions: list[dict] = field(default_factory=list)
    version_groups: list[dict] = field(default_factory=list)


class PokeAPIImporter:
    def __init__(
        self,
        client: PokeAPIClient,
        log: Callable[[str], None] = logger.info,
    ):
        self.client = client
        self.log = log

    def run(self, species_names: Iterable[str] | None = None) -> dict[str, int]:
        data = self.fetch(species_names)
        return self.save(data)

    # ------------------------------------------------------------------
    # Fase 1: busca
    # ------------------------------------------------------------------
    def fetch(self, species_names: Iterable[str] | None = None) -> FetchedData:
        species_refs = self.client.list("pokemon-species")

        if species_names:
            wanted = set(species_names)
            species_refs = [r for r in species_refs if r["name"] in wanted]
            unknown = wanted - {r["name"] for r in species_refs}

            if unknown:
                raise UnknownSpeciesError(", ".join(sorted(unknown)))

        data = FetchedData()
        data.species = self._get_many("species", (r["url"] for r in species_refs))
        data.pokemon = self._get_many(
            "pokemon",
            (v["pokemon"]["url"] for s in data.species for v in s["varieties"]),
        )
        data.forms = self._get_many(
            "forms", (f["url"] for p in data.pokemon for f in p["forms"])
        )
        # Import completo: todas as versões (jogos recentes, como Scarlet/Violet,
        # não aparecem em game_indices mas são usadas em OriginalTrainer).
        all_versions = [] if species_names else self.client.list("version")
        data.versions = self._get_many(
            "versions",
            [r["url"] for r in all_versions]
            + [gi["version"]["url"] for p in data.pokemon for gi in p["game_indices"]],
        )
        all_groups = [] if species_names else self.client.list("version-group")
        data.version_groups = self._get_many(
            "version groups",
            [r["url"] for r in all_groups]
            + [v["version_group"]["url"] for v in data.versions]
            + [f["version_group"]["url"] for f in data.forms],
        )

        return data

    def _get_many(self, label: str, urls: Iterable[str]) -> list[dict]:
        urls = list(urls)
        self.log(f"Fetching {label}...")
        return list(self.client.get_many(urls).values())

    # ------------------------------------------------------------------
    # Fase 2: gravação
    # ------------------------------------------------------------------
    @transaction.atomic
    def save(self, data: FetchedData) -> dict[str, int]:
        self.log("Saving...")

        vg_ids = self._save_version_groups(data.version_groups)
        version_ids = self._save_versions(data.versions, vg_ids)
        species_ids = self._save_species(data.species)
        pokemon_ids = self._save_pokemon(data.pokemon, species_ids, version_ids)
        self._save_forms(data.forms, pokemon_ids, vg_ids)

        # Segunda passada: referências entre espécies/pokémon.
        self._link_evolutions(data.species)
        self._link_varieties(data.species)

        return {
            "version_groups": len(vg_ids),
            "versions": len(version_ids),
            "species": len(species_ids),
            "pokemon": len(pokemon_ids),
            "forms": len(data.forms),
        }

    def _save_version_groups(self, version_groups: list[dict]) -> dict[str, int]:
        return self._upsert(
            VersionGroup,
            [
                {
                    "name": vg["name"],
                    "generation": vg["generation"]["name"],
                    "order": vg["order"],
                    "pokedexes": _names(vg["pokedexes"]),
                    "regions": _names(vg["regions"]),
                    "versions": _names(vg["versions"]),
                }
                for vg in version_groups
            ],
        )

    def _save_versions(self, versions: list[dict], vg_ids) -> dict[str, int]:
        return self._upsert(
            Version,
            [
                {
                    "name": v["name"],
                    "version_group_id": vg_ids[v["version_group"]["name"]],
                }
                for v in versions
            ],
        )

    def _save_species(self, species: list[dict]) -> dict[str, int]:
        species_ids = self._upsert(
            PokemonSpecies,
            [
                {
                    "name": s["name"],
                    "order": s["order"],
                    "gender_rate": s["gender_rate"],
                    # A PokéAPI traz null em alguns campos de espécies recentes.
                    "capture_rate": s["capture_rate"] or 0,
                    "base_happiness": s["base_happiness"] or 0,
                    "is_baby": s["is_baby"],
                    "is_legendary": s["is_legendary"],
                    "is_mythical": s["is_mythical"],
                    "hatch_counter": s["hatch_counter"] or 0,
                    "has_gender_differences": s["has_gender_differences"],
                    "forms_switchable": s["forms_switchable"],
                    "growth_rate": _name(s["growth_rate"]) or "",
                    "egg_groups": _names(s["egg_groups"]),
                    "color": _name(s["color"]) or "",
                    "shape": _name(s["shape"]) or "",
                    "generation": _name(s["generation"]) or "",
                }
                for s in species
            ],
        )

        entry_ids = self._value_ids(
            PokemonSpeciesDexEntry,
            ("pokedex", "entry_number"),
            {
                (e["pokedex"]["name"], e["entry_number"])
                for s in species
                for e in s["pokedex_numbers"]
            },
        )
        self._replace_m2m(
            PokemonSpecies.pokedex_numbers,
            species_ids.values(),
            [
                (
                    species_ids[s["name"]],
                    entry_ids[(e["pokedex"]["name"], e["entry_number"])],
                )
                for s in species
                for e in s["pokedex_numbers"]
            ],
        )

        return species_ids

    def _save_pokemon(self, pokemon: list[dict], species_ids, version_ids):
        pokemon_ids = self._upsert(
            Pokemon,
            [
                {
                    "name": p["name"],
                    "pokeapi_id": p["id"],
                    "base_experience": p["base_experience"],
                    "height": p["height"],
                    "is_default": p["is_default"],
                    "order": p["order"],
                    "weight": p["weight"],
                    "sprites": p["sprites"],
                    "cries": p.get("cries") or {},
                    "species_id": species_ids[p["species"]["name"]],
                }
                for p in pokemon
            ],
        )

        def ability_key(a):
            return (a["slot"], a["is_hidden"], a["ability"]["name"])

        def stat_key(s):
            return (s["stat"]["name"], s["effort"], s["base_stat"])

        def type_key(t):
            return (t["slot"], t["type"]["name"])

        def game_index_key(gi):
            return (version_ids[gi["version"]["name"]], gi["game_index"])

        relations = (
            (
                Pokemon.abilities,
                PokemonAbility,
                ("slot", "is_hidden", "ability"),
                "abilities",
                ability_key,
            ),
            (
                Pokemon.stats,
                PokemonStat,
                ("stat", "effort", "base_stat"),
                "stats",
                stat_key,
            ),
            (Pokemon.types, PokemonType, ("slot", "type"), "types", type_key),
            (
                Pokemon.game_indices,
                VersionGameIndex,
                ("version_id", "game_index"),
                "game_indices",
                game_index_key,
            ),
        )

        for m2m, model, fields, key, to_values in relations:
            value_ids = self._value_ids(
                model, fields, {to_values(item) for p in pokemon for item in p[key]}
            )
            self._replace_m2m(
                m2m,
                pokemon_ids.values(),
                [
                    (pokemon_ids[p["name"]], value_ids[to_values(item)])
                    for p in pokemon
                    for item in p[key]
                ],
            )

        return pokemon_ids

    def _save_forms(self, forms: list[dict], pokemon_ids, vg_ids) -> None:
        form_ids = self._upsert(
            PokemonForm,
            [
                {
                    "name": f["name"],
                    "pokeapi_id": f["id"],
                    "order": f["order"],
                    "form_order": f["form_order"],
                    "is_default": f["is_default"],
                    "is_battle_only": f["is_battle_only"],
                    "is_mega": f["is_mega"],
                    "form_name": f["form_name"],
                    "sprites": f["sprites"],
                    "version_group_id": vg_ids[f["version_group"]["name"]],
                    "pokemon_id": pokemon_ids[f["pokemon"]["name"]],
                }
                for f in forms
            ],
        )

        type_ids = self._value_ids(
            PokemonFormType,
            ("slot", "type"),
            {(t["slot"], t["type"]["name"]) for f in forms for t in f["types"]},
        )
        self._replace_m2m(
            PokemonForm.types,
            form_ids.values(),
            [
                (form_ids[f["name"]], type_ids[(t["slot"], t["type"]["name"])])
                for f in forms
                for t in f["types"]
            ],
        )

    def _link_evolutions(self, species: list[dict]) -> None:
        # Inclui espécies já existentes no banco (útil em imports parciais).
        wanted = {_name(s["evolves_from_species"]) for s in species} - {None}
        ids = dict(
            PokemonSpecies.objects.filter(
                name__in=wanted | {s["name"] for s in species}
            ).values_list("name", "id")
        )

        to_update = [
            PokemonSpecies(
                id=ids[s["name"]],
                evolves_from_species_id=ids.get(_name(s["evolves_from_species"])),
            )
            for s in species
        ]
        PokemonSpecies.objects.bulk_update(
            to_update, ["evolves_from_species"], batch_size=BATCH_SIZE
        )

    def _link_varieties(self, species: list[dict]) -> None:
        pairs = [
            (s["name"], v["pokemon"]["name"], v["is_default"])
            for s in species
            for v in s["varieties"]
        ]
        pokemon_ids = dict(
            Pokemon.objects.filter(name__in={p for _, p, _ in pairs}).values_list(
                "name", "id"
            )
        )
        species_ids = dict(
            PokemonSpecies.objects.filter(
                name__in={s for s, _, _ in pairs}
            ).values_list("name", "id")
        )

        existing = {
            v.pokemon_id: v
            for v in PokemonSpeciesVariety.objects.filter(
                pokemon_id__in=pokemon_ids.values()
            )
        }
        to_create, to_update = [], []

        for _, pokemon_name, is_default in pairs:
            pokemon_id = pokemon_ids[pokemon_name]
            variety = existing.get(pokemon_id)

            if variety is None:
                variety = PokemonSpeciesVariety(
                    pokemon_id=pokemon_id, is_default=is_default
                )
                existing[pokemon_id] = variety
                to_create.append(variety)
            elif variety.is_default != is_default:
                variety.is_default = is_default
                to_update.append(variety)

        PokemonSpeciesVariety.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
        PokemonSpeciesVariety.objects.bulk_update(
            to_update, ["is_default"], batch_size=BATCH_SIZE
        )

        self._replace_m2m(
            PokemonSpecies.varieties,
            species_ids.values(),
            [(species_ids[s], existing[pokemon_ids[p]].pk) for s, p, _ in pairs],
        )

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------
    def _upsert(self, model: type[models.Model], rows: list[dict]) -> dict[str, int]:
        """Insere ou atualiza por ``name``; retorna ``{name: id}``."""
        if not rows:
            return {}

        update_fields = [k for k in rows[0] if k != "name"] + ["updated_at"]
        model.objects.bulk_create(
            [model(**row) for row in rows],
            update_conflicts=True,
            unique_fields=["name"],
            update_fields=update_fields,
            batch_size=BATCH_SIZE,
        )
        self.log(f"  {model._meta.verbose_name_plural}: {len(rows)}")

        return dict(
            model.objects.filter(name__in=[r["name"] for r in rows]).values_list(
                "name", "id"
            )
        )

    def _value_ids(
        self, model: type[models.Model], fields: tuple[str, ...], values: set[tuple]
    ) -> dict[tuple, int]:
        """IDs de linhas compartilhadas identificadas pelos valores dos campos.

        Reaproveita as existentes e cria em lote só as que faltam.
        """

        def existing() -> dict[tuple, int]:
            result = {}
            for *key, pk in model.objects.values_list(*fields, "id").order_by("id"):
                result.setdefault(tuple(key), pk)
            return result

        ids = existing()
        missing = [
            model(**dict(zip(fields, value))) for value in values if value not in ids
        ]

        if missing:
            model.objects.bulk_create(missing, batch_size=BATCH_SIZE)
            ids = existing()

        return ids

    def _replace_m2m(self, descriptor, owner_ids: Iterable[int], pairs) -> None:
        """Substitui as ligações M2M dos donos informados pelas ``pairs``."""
        m2m_field = descriptor.field
        through = descriptor.through
        source = m2m_field.m2m_field_name()
        target = m2m_field.m2m_reverse_field_name()

        through.objects.filter(**{f"{source}_id__in": list(owner_ids)}).delete()
        through.objects.bulk_create(
            [
                through(**{f"{source}_id": owner, f"{target}_id": value})
                for owner, value in dict.fromkeys(pairs)
            ],
            batch_size=BATCH_SIZE,
        )
