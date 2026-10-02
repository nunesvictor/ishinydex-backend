from django.test import TestCase

from core.tests import factories as f
from pokedex.importer import PokeAPIImporter, UnknownSpeciesError
from pokedex.models import (
    Pokemon,
    PokemonAbility,
    PokemonForm,
    PokemonSpecies,
    PokemonSpeciesVariety,
    PokemonStat,
    Version,
    VersionGameIndex,
    VersionGroup,
)
from pokedex.tests.pokeapi_fixtures import FakePokeAPIClient


class ImporterTestCase(TestCase):
    def setUp(self):
        self.client_api = FakePokeAPIClient()
        self.importer = PokeAPIImporter(
            self.client_api, log=lambda msg: None  # type: ignore[arg-type]
        )

    def run_import(self, species=None):
        return self.importer.run(species)


class FullImportTests(ImporterTestCase):
    def setUp(self):
        super().setUp()
        self.counts = self.run_import()

    def test_counts(self):
        self.assertEqual(
            self.counts,
            {
                "version_groups": 4,
                "versions": 4,
                "species": 3,
                "pokemon": 4,
                "forms": 5,
            },
        )
        self.assertEqual(PokemonForm.objects.count(), 5)

    def test_version_groups_and_versions(self):
        red_blue = VersionGroup.objects.get(name="red-blue")

        self.assertEqual(red_blue.generation, "generation-i")
        self.assertEqual(red_blue.versions, ["red", "blue"])
        self.assertEqual(red_blue.pokedexes, ["kanto"])
        self.assertEqual(
            Version.objects.get(name="gold").version_group.name, "gold-silver"
        )

    def test_full_import_brings_all_versions(self):
        """Versões sem game index (ex.: jogos recentes) também são importadas."""
        self.assertEqual(
            Version.objects.get(name="sword").version_group.name, "sword-shield"
        )
        self.assertTrue(
            VersionGroup.objects.filter(name="brilliant-diamond-shining-pearl").exists()
        )

    def test_species_fields(self):
        pikachu = PokemonSpecies.objects.get(name="pikachu")

        self.assertEqual(pikachu.growth_rate, "medium")
        self.assertEqual(pikachu.color, "yellow")
        self.assertEqual(pikachu.shape, "quadruped")
        self.assertEqual(pikachu.egg_groups, ["ground", "fairy"])
        self.assertTrue(pikachu.has_gender_differences)
        self.assertEqual(
            list(pikachu.pokedex_numbers.values_list("pokedex", "entry_number")),
            [("national", 25)],
        )

    def test_pre_evolution_listed_later_is_linked(self):
        """Regressão: o Pichu vem depois do Pikachu, e o vínculo ficava vazio."""
        species = {s.name: s for s in PokemonSpecies.objects.all()}

        self.assertEqual(species["pikachu"].evolves_from_species, species["pichu"])
        self.assertEqual(species["raichu"].evolves_from_species, species["pikachu"])
        self.assertIsNone(species["pichu"].evolves_from_species)

    def test_varieties(self):
        pikachu = PokemonSpecies.objects.get(name="pikachu")

        self.assertEqual(
            sorted(pikachu.varieties.values_list("pokemon__name", "is_default")),
            [("pikachu", True), ("pikachu-gmax", False)],
        )
        self.assertEqual(
            set(pikachu.pokemons.values_list("name", flat=True)),
            {"pikachu", "pikachu-gmax"},
        )

    def test_pokemon_fields_and_relations(self):
        pikachu = Pokemon.objects.get(name="pikachu")

        self.assertEqual(pikachu.pokeapi_id, 25)
        self.assertEqual(pikachu.weight, 60)
        self.assertEqual(
            pikachu.sprites["other"]["official-artwork"]["front_default"],
            "https://art/25.png",
        )
        self.assertEqual(pikachu.cries, {"latest": "https://cries/25.ogg"})
        self.assertEqual([str(t) for t in pikachu.types.all()], ["electric"])
        self.assertEqual(
            sorted(pikachu.abilities.values_list("ability", "slot", "is_hidden")),
            [("lightning-rod", 3, True), ("static", 1, False)],
        )
        self.assertEqual(
            sorted(str(s) for s in pikachu.stats.all()), ["hp: 35", "speed: 90"]
        )
        self.assertEqual(
            sorted(str(gi) for gi in pikachu.game_indices.all()),
            ["blue#84", "gold#156", "red#84"],
        )

    def test_forms(self):
        spiky = PokemonForm.objects.get(name="pichu-spiky-eared")

        self.assertEqual(spiky.pokemon.name, "pichu")
        self.assertFalse(spiky.is_default)
        self.assertEqual(spiky.form_name, "spiky-eared")
        self.assertEqual(spiky.version_group.name, "gold-silver")
        self.assertEqual([str(t) for t in spiky.types.all()], ["electric"])
        self.assertEqual(spiky.pokeapi_id, 10077)

    def test_shared_rows_are_reused(self):
        # "static" slot 1 é usada por 4 pokémon; "hp 35" por 2.
        self.assertEqual(PokemonAbility.objects.filter(ability="static").count(), 1)
        self.assertEqual(PokemonStat.objects.filter(stat="hp", base_stat=35).count(), 1)

    def test_moves_are_not_imported(self):
        self.assertFalse(any(p.startswith("move/") for p in self.client_api.requested))
        self.assertFalse(Pokemon.objects.get(name="pikachu").moves.exists())


class ReimportTests(ImporterTestCase):
    def test_running_twice_does_not_duplicate(self):
        self.run_import()
        counts = {
            model: model.objects.count()
            for model in (
                Pokemon,
                PokemonForm,
                PokemonSpecies,
                PokemonSpeciesVariety,
                PokemonAbility,
                PokemonStat,
                VersionGameIndex,
                Pokemon.abilities.through,
                Pokemon.game_indices.through,
                PokemonSpecies.varieties.through,
            )
        }

        self.run_import()

        for model, count in counts.items():
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), count)

    def test_updates_changed_fields_and_relations(self):
        self.run_import()
        pikachu = self.client_api.resource("pokemon", "pikachu")
        pikachu["weight"] = 61
        pikachu["abilities"] = pikachu["abilities"][:1]
        self.client_api.resource("pokemon-species", "pikachu")[
            "evolves_from_species"
        ] = None

        self.run_import()

        pokemon = Pokemon.objects.get(name="pikachu")
        self.assertEqual(pokemon.weight, 61)
        self.assertEqual(
            list(pokemon.abilities.values_list("ability", flat=True)), ["static"]
        )
        self.assertIsNone(
            PokemonSpecies.objects.get(name="pikachu").evolves_from_species
        )

    def test_updates_legacy_rows_created_by_the_old_notebook(self):
        legacy = f.make_species(name="pikachu", color="None")

        self.run_import()

        legacy.refresh_from_db()
        self.assertEqual(legacy.color, "yellow")
        self.assertEqual(PokemonSpecies.objects.filter(name="pikachu").count(), 1)


class PartialImportTests(ImporterTestCase):
    def test_only_requested_species_and_their_dependencies(self):
        counts = self.run_import(["raichu"])

        self.assertEqual(counts["species"], 1)
        self.assertFalse(Version.objects.filter(name="sword").exists())
        self.assertEqual(
            list(Pokemon.objects.values_list("name", flat=True)), ["raichu"]
        )
        self.assertFalse(
            any("pichu" in p or p.endswith("/25") for p in self.client_api.requested)
        )

    def test_evolution_resolved_against_species_already_in_db(self):
        self.run_import(["pikachu"])
        self.assertIsNone(
            PokemonSpecies.objects.get(name="pikachu").evolves_from_species
        )

        self.run_import(["raichu", "pichu"])

        self.assertEqual(
            PokemonSpecies.objects.get(name="raichu").evolves_from_species.name,
            "pikachu",
        )

    def test_unknown_species(self):
        with self.assertRaisesMessage(UnknownSpeciesError, "missingno"):
            self.run_import(["pikachu", "missingno"])

        self.assertFalse(PokemonSpecies.objects.exists())

    def test_failure_rolls_back(self):
        del self.client_api.resource("pokemon", "pichu")["weight"]

        with self.assertRaises(KeyError):
            self.run_import()

        self.assertFalse(Pokemon.objects.exists())
        self.assertFalse(VersionGroup.objects.exists())
