import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from catalog import build as catalog
from core.tests import factories as f
from home.models import HOME_ORIGIN_VERSIONS, HOME_TRANSFER_VERSIONS
from pokedex.models import PokemonAbility, PokemonSpeciesDexEntry


class CatalogTests(TestCase):
    """Pacote do catálogo (``build_catalog`` e ``exportcatalog``)."""

    @classmethod
    def setUpTestData(cls):
        sv = f.make_version_group(
            name="scarlet-violet",
            generation="generation-ix",
            versions=["scarlet"],
            pokedexes=["paldea", "kitakami"],
            order=25,
        )
        f.make_version(name="scarlet", version_group=sv)
        f.make_version(name="yellow")
        # Grupo da DLC: marca a pokédex dela; não recebe do HOME.
        f.make_version_group(
            name="the-teal-mask",
            versions=["the-teal-mask-scarlet"],
            pokedexes=["kitakami"],
            order=26,
        )
        bdsp = f.make_version_group(
            name="brilliant-diamond-shining-pearl",
            versions=["brilliant-diamond"],
            pokedexes=["original-sinnoh"],
            order=23,
        )
        f.make_version(name="brilliant-diamond", version_group=bdsp)
        cls.bulba_species, cls.bulba, cls.bulba_form = f.make_full_pokemon(
            "bulbasaur", 1, types=("grass", "poison"), national_dex=1
        )
        cls.bulba.abilities.add(
            PokemonAbility.objects.create(slot=3, ability="chlorophyll", is_hidden=True)
        )
        for stat, value in (("speed", 45), ("hp", 45), ("attack", 49)):
            f.make_stat(cls.bulba, stat, value)
        ivy_species, _, cls.ivy_form = f.make_full_pokemon("ivysaur", 2, national_dex=2)
        ivy_species.evolves_from_species = cls.bulba_species
        ivy_species.save()
        for species, dex, number in (
            (cls.bulba_species, "paldea", 9),
            (ivy_species, "kitakami", 3),
            (ivy_species, "paldea", 10),
            (ivy_species, "original-sinnoh", 1),
        ):
            species.pokedex_numbers.add(
                PokemonSpeciesDexEntry.objects.create(entry_number=number, pokedex=dex)
            )
        # Forma só de batalha: fica fora do dex padrão.
        cls.battle = f.make_form(
            cls.bulba,
            name="bulbasaur-battle",
            pokeapi_id=10001,
            is_default=False,
            is_battle_only=True,
            version_group=sv,
        )

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.locks = self.tmp / "locks.json"
        self.write_locks(["ivysaur", "bulbasaur"])
        patcher = mock.patch.object(catalog, "SHINY_LOCKS_FILE", self.locks)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.exclusives = self.tmp / "exclusives.json"
        self.write_exclusives("scarlet", "the-teal-mask", ["ivysaur"])
        patcher = mock.patch.object(catalog, "VERSION_EXCLUSIVES_FILE", self.exclusives)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.encounters = self.tmp / "encounters.json"
        self.write_encounters(["bulbasaur"])
        patcher = mock.patch.object(catalog, "SPECIAL_ENCOUNTERS_FILE", self.encounters)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.game_forms = self.tmp / "regional.json"
        self.write_game_data(self.game_forms, "games", "versionGroup", "scarlet-violet")
        patcher = mock.patch.object(catalog, "REGIONAL_FORMS_FILE", self.game_forms)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.game_locks = self.tmp / "game_locks.json"
        self.write_game_data(self.game_locks, "locks", "version", "scarlet")
        patcher = mock.patch.object(catalog, "GAME_SHINY_LOCKS_FILE", self.game_locks)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cutoffs = self.tmp / "cutoffs.json"
        self.write_cutoffs()
        patcher = mock.patch.object(catalog, "HOME_CUTOFFS_FILE", self.cutoffs)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.methods = self.tmp / "methods.json"
        self.write_methods()
        patcher = mock.patch.object(catalog, "SHINY_METHODS_FILE", self.methods)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.odds = self.tmp / "odds.json"
        self.write_odds()
        patcher = mock.patch.object(catalog, "SHINY_ODDS_FILE", self.odds)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_cutoffs(self, *cutoffs):
        self.cutoffs.write_text(
            json.dumps({"sources": [], "notes": [], "cutoffs": list(cutoffs)})
        )

    def write_methods(self, *methods):
        methods = methods or (
            {
                "id": "sr",
                "label": "Soft reset",
                "units": ["resets", "hours"],
                "versions": ["scarlet"],
            },
        )
        self.methods.write_text(
            json.dumps({"sources": [], "notes": [], "methods": list(methods)})
        )

    SR_ODDS = {
        "method": "sr",
        "versions": ["scarlet"],
        "kind": "rolls",
        "base": 4096,
        "rolls": 1,
        "charm": 2,
        "modifiers": [],
        "charmExceptForms": ["ivysaur"],
        "note": "Nota.",
        "sources": ["https://exemplo"],
    }

    def write_odds(self, *rules):
        rules = rules or (self.SR_ODDS,)
        self.odds.write_text(
            json.dumps({"sources": [], "notes": [], "rules": list(rules)})
        )

    @staticmethod
    def write_game_data(file, key, field, value, forms=("ivysaur",)):
        """Arquivo de formas por jogo ou de locks por jogo."""
        file.write_text(
            json.dumps(
                {
                    "sources": [],
                    "notes": [],
                    key: [{field: value, "forms": list(forms)}],
                }
            )
        )

    def write_encounters(self, species, dlc: str | None = "the-teal-mask"):
        encounter = {"label": "Especial", "dlc": dlc, "species": species}
        self.encounters.write_text(
            json.dumps(
                {
                    "sources": [],
                    "notes": [],
                    "encounters": [
                        encounter
                        | {"name": "special", "versionGroup": "scarlet-violet"},
                        # Jogo que não recebe do HOME: fica de fora.
                        encounter | {"name": "other", "versionGroup": "red-blue"},
                    ],
                }
            )
        )

    def write_exclusives(self, version, dlc, forms):
        self.exclusives.write_text(
            json.dumps(
                {
                    "sources": [],
                    "notes": [],
                    "exclusives": [{"version": version, "dlc": dlc, "forms": forms}],
                }
            )
        )

    def write_locks(self, forms):
        self.locks.write_text(
            json.dumps(
                [
                    {
                        "caption": "Seeds",
                        "description": "",
                        "lockType": "distro-only",
                        "active": True,
                        "forms": forms,
                    }
                ]
            )
        )

    def test_forms_pokemon_species_and_sprites(self):
        data = catalog.build_catalog("catalog-2026.10.03")

        self.assertEqual(data["schemaVersion"], catalog.SCHEMA_VERSION)
        self.assertEqual(data["version"], "catalog-2026.10.03")
        forms = {form["name"]: form for form in data["forms"]}
        self.assertEqual(
            forms["bulbasaur"],
            {
                "id": 1,
                "name": "bulbasaur",
                "formName": "",
                "pokemon": 1,
                "formOrder": 1,
                "isDefault": True,
                "isBattleOnly": False,
                "isMega": False,
                "versionGroup": self.bulba_form.version_group.name,
                "types": ["grass", "poison"],
                "sprite": "pokemon/other/home/1.png",
                "shinySprite": "pokemon/other/home/shiny/1.png",
            },
        )
        self.assertTrue(forms["bulbasaur-battle"]["isBattleOnly"])

        bulba = next(p for p in data["pokemon"] if p["name"] == "bulbasaur")
        self.assertEqual(bulba["species"], "bulbasaur")
        # Status na ordem dos jogos; habilidades pelo slot.
        self.assertEqual([s["stat"] for s in bulba["stats"]], ["hp", "attack", "speed"])
        self.assertEqual(
            bulba["abilities"],
            [{"ability": "chlorophyll", "slot": 3, "isHidden": True}],
        )

        species = {s["name"]: s for s in data["species"]}
        self.assertEqual(species["bulbasaur"]["nationalNumber"], 1)
        self.assertEqual(species["ivysaur"]["evolvesFrom"], "bulbasaur")
        self.assertIsNone(species["bulbasaur"]["evolvesFrom"])

    def test_versions_default_dex_choices_and_locks(self):
        data = catalog.build_catalog("v")

        groups = {g["name"]: g for g in data["versionGroups"]}
        self.assertEqual(groups["scarlet-violet"]["originMark"], "paldea")
        self.assertEqual(groups["scarlet-violet"]["versions"], ["scarlet"])
        versions = {v["name"]: v for v in data["versions"]}
        self.assertTrue(versions["scarlet"]["receivesFromHome"])
        self.assertFalse(versions["yellow"]["receivesFromHome"])

        self.assertEqual(data["defaultDex"], [1, 2])  # sem a forma de batalha

        choices = data["choices"]
        self.assertIn(
            {
                "value": "poke-ball",
                "label": "Poké Ball",
                "sprite": "items/poke-ball.png",
            },
            choices["pokeball"],
        )
        water = next(t for t in choices["type"] if t["value"] == "water")
        self.assertEqual(
            water, {"value": "water", "label": "Água", "sprite": water["sprite"]}
        )
        self.assertTrue(
            water["sprite"].startswith("types/") and "/small/11.png" in water["sprite"]
        )
        modest = next(n for n in choices["nature"] if n["value"] == "modest")
        self.assertEqual(
            (modest["increased"], modest["decreased"]), ("special-attack", "attack")
        )

        self.assertEqual(
            data["shinyLocks"],
            [
                {
                    "caption": "Seeds",
                    "description": "",
                    "lockType": "distro-only",
                    "active": True,
                    "forms": [1, 2],
                }
            ],
        )

    def test_frlg_is_an_origin_but_not_a_save(self):
        # FRLG do Switch (HOME 4.1.0): só ida, como o Bank. Entra nas pokédex
        # (caçadas, exclusivos, locks) e na marca GBA, mas não recebe do HOME.
        frlg = f.make_version_group(
            name="firered-leafgreen",
            generation="generation-iii",
            versions=["firered"],
            pokedexes=["kanto"],
            order=10,
        )
        f.make_version(name="firered", version_group=frlg)
        self.bulba_species.pokedex_numbers.add(
            PokemonSpeciesDexEntry.objects.create(entry_number=1, pokedex="kanto")
        )
        data = catalog.build_catalog("v")

        versions = {v["name"]: v for v in data["versions"]}
        self.assertFalse(versions["firered"]["receivesFromHome"])
        groups = {g["name"]: g for g in data["versionGroups"]}
        self.assertEqual(groups["firered-leafgreen"]["originMark"], "gba")
        dexes = {d["name"]: d for d in data["pokedexes"]}
        self.assertEqual(
            dexes["kanto"],
            {
                "name": "kanto",
                "label": "Kanto",
                "versionGroups": ["firered-leafgreen"],
                "dlc": None,
                "entries": [["bulbasaur", 1]],
            },
        )

    def test_bank_games_are_origins_but_not_saves(self):
        # Gen VI e VII (backend#107): só ida, pelo Pokémon Bank. Entram nas
        # pokédex (com o nome em pt-BR), nos exclusivos e nos locks, com a
        # marca do jogo, mas não recebem do HOME.
        oras = f.make_version_group(
            name="omega-ruby-alpha-sapphire",
            generation="generation-vi",
            versions=["omega-ruby"],
            pokedexes=["updated-hoenn"],
            order=18,
        )
        f.make_version(name="omega-ruby", version_group=oras)
        sm = f.make_version_group(
            name="sun-moon",
            generation="generation-vii",
            versions=["sun"],
            pokedexes=["original-alola", "original-melemele"],
            order=19,
        )
        f.make_version(name="sun", version_group=sm)
        for dex in ("updated-hoenn", "original-alola", "original-melemele"):
            self.bulba_species.pokedex_numbers.add(
                PokemonSpeciesDexEntry.objects.create(entry_number=1, pokedex=dex)
            )
        self.write_exclusives("sun", None, ["bulbasaur"])
        self.write_game_data(
            self.game_locks, "locks", "version", "omega-ruby", ["bulbasaur"]
        )
        data = catalog.build_catalog("v")

        versions = {v["name"]: v for v in data["versions"]}
        self.assertFalse(versions["omega-ruby"]["receivesFromHome"])
        self.assertFalse(versions["sun"]["receivesFromHome"])
        groups = {g["name"]: g for g in data["versionGroups"]}
        self.assertEqual(groups["omega-ruby-alpha-sapphire"]["originMark"], "kalos")
        self.assertEqual(groups["sun-moon"]["originMark"], "alola")
        dexes = {d["name"]: d for d in data["pokedexes"]}
        self.assertEqual(
            [
                (dexes[name]["label"], dexes[name]["versionGroups"])
                for name in ("updated-hoenn", "original-alola", "original-melemele")
            ],
            [
                ("Hoenn", ["omega-ruby-alpha-sapphire"]),
                ("Alola", ["sun-moon"]),
                ("Melemele", ["sun-moon"]),
            ],
        )
        self.assertEqual(
            data["versionExclusives"],
            [{"version": "sun", "dlc": None, "forms": [self.bulba_form.pokeapi_id]}],
        )
        self.assertEqual(
            data["gameShinyLocks"],
            [{"version": "omega-ruby", "forms": [self.bulba_form.pokeapi_id]}],
        )

    @staticmethod
    def make_victini():
        """Geração 5: fora da nacional do BDSP e de qualquer pokédex."""
        f.make_full_pokemon("victini", 494, national_dex=494)

    def test_pokedexes_of_home_games(self):
        self.make_victini()
        data = catalog.build_catalog("v")

        dexes = {d["name"]: d for d in data["pokedexes"]}
        # Só as dos jogos do HOME, na ordem dos grupos; a nacional do BDSP é
        # derivada (até o nº 493: o Victini fica de fora).
        self.assertEqual(
            list(dexes),
            ["original-sinnoh", "bdsp-national", "paldea", "kitakami", "special"],
        )
        # Pokédex especial: sem número.
        self.assertEqual(
            dexes["special"],
            {
                "name": "special",
                "label": "Especial",
                "versionGroups": ["scarlet-violet"],
                "dlc": "the-teal-mask",
                "entries": [["bulbasaur", None]],
            },
        )
        self.assertEqual(
            dexes["paldea"],
            {
                "name": "paldea",
                "label": "Paldea",
                "versionGroups": ["scarlet-violet"],
                "dlc": None,
                "entries": [["bulbasaur", 9], ["ivysaur", 10]],
            },
        )
        self.assertEqual(dexes["kitakami"]["dlc"], "the-teal-mask")
        self.assertEqual(dexes["kitakami"]["entries"], [["ivysaur", 3]])
        self.assertEqual(dexes["original-sinnoh"]["label"], "Sinnoh")
        self.assertEqual(
            dexes["bdsp-national"],
            {
                "name": "bdsp-national",
                "label": "Nacional",
                "versionGroups": ["brilliant-diamond-shining-pearl"],
                "dlc": None,
                "entries": [["bulbasaur", 1], ["ivysaur", 2]],
            },
        )

        self.assertEqual(
            data["versionExclusives"],
            [{"version": "scarlet", "dlc": "the-teal-mask", "forms": [2]}],
        )
        self.assertEqual(
            data["gameForms"], [{"versionGroup": "scarlet-violet", "forms": [2]}]
        )
        self.assertEqual(data["gameShinyLocks"], [{"version": "scarlet", "forms": [2]}])
        self.assertEqual(
            data["shinyMethods"],
            [
                {
                    "id": "sr",
                    "label": "Soft reset",
                    "units": ["resets", "hours"],
                    "versions": ["scarlet"],
                }
            ],
        )
        self.assertEqual(data["schemaVersion"], 1)

    def test_pokedex_without_label_uses_its_name(self):
        f.make_version_group(
            name="legends-za", versions=["legends-za"], pokedexes=["new-dex"]
        )
        data = catalog.build_catalog("v")
        new = next(d for d in data["pokedexes"] if d["name"] == "new-dex")
        self.assertEqual(new["label"], "New Dex")

    def test_bad_special_encounters_fail(self):
        for species, dlc, message in (
            (["missingno"], None, "espécies desconhecidas"),
            (["bulbasaur"], "the-big-dlc", "DLC desconhecida"),
        ):
            with self.subTest(message=message):
                self.write_encounters(species, dlc)
                with self.assertRaisesRegex(catalog.CatalogError, message):
                    catalog.build_catalog("v")

    def test_bad_exclusives_fail(self):
        self.make_victini()
        cases = [
            (("scarlet", None, ["missingno"]), "formas desconhecidas"),
            (("yellow", None, ["ivysaur"]), "sem pokédex: yellow"),
            (("scarlet", "the-big-dlc", ["ivysaur"]), "DLC desconhecida"),
            (("brilliant-diamond", None, ["victini"]), "fora das pokédex"),
        ]
        for args, message in cases:
            with self.subTest(message=message):
                self.write_exclusives(*args)
                with self.assertRaisesRegex(catalog.CatalogError, message):
                    catalog.build_catalog("v")

    def test_bad_game_data_fails(self):
        self.make_victini()
        for file, key, field in (
            (self.game_forms, "games", "versionGroup"),
            (self.game_locks, "locks", "version"),
        ):
            good = "scarlet-violet" if field == "versionGroup" else "scarlet"
            cases = [
                ((good, ["missingno"]), "formas desconhecidas"),
                (("yellow", ["ivysaur"]), "sem pokédex: yellow"),
                ((good, ["victini"]), "fora das pokédex"),
            ]
            for (value, forms), message in cases:
                with self.subTest(file=file.name, message=message):
                    self.write_game_data(file, key, field, value, forms)
                    with self.assertRaisesRegex(catalog.CatalogError, message):
                        catalog.build_catalog("v")
            self.write_game_data(file, key, field, good)

    def test_home_cutoffs(self):
        sm = f.make_version_group(
            name="sun-moon",
            generation="generation-vii",
            versions=["sun"],
            pokedexes=["original-alola"],
            order=19,
        )
        f.make_version(name="sun", version_group=sm)
        until = "2027-02-26T03:00:00Z"
        self.write_cutoffs({"reason": "Bank", "homeUntil": until, "versions": ["sun"]})

        versions = {v["name"]: v for v in catalog.build_catalog("v")["versions"]}
        self.assertEqual(versions["sun"]["homeUntil"], until)
        # Nos outros jogos, a chave não aparece.
        self.assertNotIn("homeUntil", versions["scarlet"])

        cases = [
            ({"homeUntil": "amanhã", "versions": ["sun"]}, "data de corte"),
            ({"homeUntil": "2027-02-26T03:00:00", "versions": ["sun"]}, "UTC"),
            ({"homeUntil": "2027-02-26T03:00:00-03:00", "versions": ["sun"]}, "UTC"),
            ({"homeUntil": until, "versions": ["scarlet"]}, "só de ida: scarlet"),
            ({"homeUntil": until, "versions": ["moon"]}, "só de ida: moon"),
            ({"homeUntil": until, "versions": ["sun", "sun"]}, "repetido: sun"),
        ]
        for cutoff, message in cases:
            with self.subTest(message=message):
                self.write_cutoffs(cutoff)
                with self.assertRaisesRegex(catalog.CatalogError, message):
                    catalog.build_catalog("v")

    def test_bad_shiny_methods_fail(self):
        good = {"id": "sr", "label": "SR", "units": ["resets"], "versions": ["scarlet"]}
        cases = [
            ((good, good), "repetido: sr"),
            ((good | {"units": []},), "unidades inválidas"),
            ((good | {"units": ["laps"]},), "unidades inválidas"),
            ((good | {"versions": ["scarlet", "gold"]},), r"desconhecidas.*gold"),
        ]
        for methods, message in cases:
            with self.subTest(message=message):
                self.write_methods(*methods)
                with self.assertRaisesRegex(catalog.CatalogError, message):
                    catalog.build_catalog("v")

    def test_shiny_odds_with_form_ids(self):
        data = catalog.build_catalog("v")

        rule = {k: v for k, v in self.SR_ODDS.items() if k != "sources"}
        self.assertEqual(data["shinyOdds"], [rule | {"charmExceptForms": [2]}])

    def test_bad_shiny_odds_fail(self):
        good = self.SR_ODDS | {"charmExceptForms": []}
        choice = {
            "id": "a",
            "label": "A",
            "type": "choice",
            "options": [{"label": "x", "rolls": 0}, {"label": "y", "rolls": 1}],
        }
        number = {"id": "n", "label": "N", "type": "number", "min": 0, "max": 9}
        chance = good | {"kind": "chance", "rolls": None}
        cases = [
            ((good | {"method": "dexnav"},), "método desconhecido: dexnav"),
            ((good | {"versions": ["yellow"]},), r"fora dos jogos.*yellow"),
            ((good, good), "repetidas: sr em scarlet"),
            ((good | {"kind": "magic"},), "tipo ou base inválidos"),
            ((good | {"base": 100},), "tipo ou base inválidos"),
            ((good | {"rolls": 0},), "sem sorteios"),
            ((chance,), "sem chance"),
            ((good | {"chain": {"steps": []}},), "fora de ordem"),
            (
                (good | {"chain": {"steps": [{"from": 1, "rolls": 0}]}},),
                "fora de ordem",
            ),
            ((chance | {"chain": {"steps": [{"from": 0, "rolls": 1}]}},), "sem odds"),
            ((good | {"modifiers": [choice, choice]},), "repetido em sr"),
            ((good | {"modifiers": [choice | {"options": []}]},), "sem opções"),
            ((good | {"modifiers": [number | {"min": 9}]},), "faixa inválida"),
            ((good | {"modifiers": [choice | {"type": "slider"}]},), "tipo de mod"),
            (
                (
                    good
                    | {
                        "modifiers": [number | {"when": {"modifier": "a", "option": 0}}]
                    },
                ),
                "condição inválida",
            ),
            (
                (
                    good
                    | {
                        "modifiers": [
                            choice,
                            number | {"when": {"modifier": "a", "option": 2}},
                        ]
                    },
                ),
                "condição inválida",
            ),
            (
                (
                    chance
                    | {
                        "modifiers": [choice],
                        "table": {"rows": "a", "columns": "n", "odds": [[1]]},
                    },
                ),
                "tabela",
            ),
            (
                (
                    chance
                    | {
                        "modifiers": [choice, choice | {"id": "b"}],
                        "table": {"rows": "a", "columns": "b", "odds": [[1, 2]]},
                    },
                ),
                "tabela",
            ),
            (
                (
                    chance
                    | {
                        "modifiers": [choice, choice | {"id": "b"}],
                        "table": {"rows": "a", "columns": "b", "odds": [[1, 2], [3]]},
                    },
                ),
                "tabela",
            ),
            ((good | {"charmExceptForms": ["missingno"]},), "missingno"),
        ]
        for rules, message in cases:
            with self.subTest(message=message):
                self.write_odds(*rules)
                with self.assertRaisesRegex(catalog.CatalogError, message):
                    catalog.build_catalog("v")
        valid = chance | {
            "odds": 300,
            "modifiers": [choice, choice | {"id": "b"}],
            "table": {"rows": "a", "columns": "b", "odds": [[1, None], [3, 4]]},
            "chain": {"steps": [{"from": 0, "odds": 9}]},
        }
        self.write_odds(valid)
        self.assertEqual(catalog.build_catalog("v")["shinyOdds"][0]["odds"], 300)

    def test_unknown_lock_form_fails(self):
        self.write_locks(["bulbasaur", "missingno"])

        with self.assertRaisesRegex(catalog.CatalogError, "missingno"):
            catalog.build_catalog("v")
        with self.assertRaisesRegex(CommandError, "missingno"):
            call_command("exportcatalog", "--output", str(self.tmp), stdout=StringIO())

    def test_command_writes_compact_json(self):
        out = StringIO()
        call_command(
            "exportcatalog",
            "--output",
            str(self.tmp / "out"),
            "--catalog-version",
            "catalog-2026.01.02",
            stdout=out,
        )

        file = self.tmp / "out" / "catalog.json"
        data = json.loads(file.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "catalog-2026.01.02")
        self.assertNotIn("\n", file.read_text(encoding="utf-8"))
        self.assertIn("catalog-2026.01.02", out.getvalue())
        self.assertIn("forms=3", out.getvalue())


class ShippedVersionExclusivesTests(TestCase):
    def test_file_is_well_formed(self):
        data = json.loads(catalog.VERSION_EXCLUSIVES_FILE.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"sources", "notes", "exclusives"})
        self.assertTrue(data["sources"])
        game = {
            "lets-go-pikachu": "lgpe",
            "lets-go-eevee": "lgpe",
            "sword": "swsh",
            "shield": "swsh",
            "brilliant-diamond": "bdsp",
            "shining-pearl": "bdsp",
            "scarlet": "sv",
            "violet": "sv",
            "firered": "frlg",
            "leafgreen": "frlg",
            "x": "xy",
            "y": "xy",
            "omega-ruby": "oras",
            "alpha-sapphire": "oras",
            "sun": "sm",
            "moon": "sm",
            "ultra-sun": "usum",
            "ultra-moon": "usum",
        }
        seen = set()
        for group in data["exclusives"]:
            with self.subTest(version=group["version"], dlc=group["dlc"]):
                self.assertEqual(set(group), {"version", "dlc", "forms"})
                self.assertIn(group["dlc"], (None, *catalog.DLC_VERSION_GROUPS))
                self.assertTrue(group["forms"])
                # Uma forma não é exclusiva das duas versões do mesmo jogo.
                for form in group["forms"]:
                    key = (game[group["version"]], form)
                    self.assertNotIn(key, seen)
                    seen.add(key)


class ShippedGameDataTests(TestCase):
    def test_files_are_well_formed(self):
        for file, key, field in (
            (catalog.REGIONAL_FORMS_FILE, "games", "versionGroup"),
            (catalog.GAME_SHINY_LOCKS_FILE, "locks", "version"),
        ):
            data = json.loads(file.read_text(encoding="utf-8"))
            with self.subTest(file=file.name):
                self.assertEqual(set(data), {"sources", "notes", key})
                self.assertTrue(data["sources"])
                values = [entry[field] for entry in data[key]]
                self.assertEqual(len(values), len(set(values)))
                for entry in data[key]:
                    self.assertEqual(set(entry), {field, "forms"})
                    self.assertEqual(entry["forms"], sorted(set(entry["forms"])))


class ShippedShinyMethodsTests(TestCase):
    def test_file_is_well_formed(self):
        data = json.loads(catalog.SHINY_METHODS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"sources", "notes", "methods"})
        self.assertTrue(data["sources"])
        ids = [m["id"] for m in data["methods"]]
        self.assertEqual(len(ids), len(set(ids)))
        for method in data["methods"]:
            with self.subTest(id=method["id"]):
                self.assertEqual(set(method), {"id", "label", "units", "versions"})
                self.assertTrue(method["units"])
                self.assertLessEqual(set(method["units"]), catalog.SHINY_METHOD_UNITS)
                self.assertTrue(method["versions"])
                self.assertEqual(len(method["versions"]), len(set(method["versions"])))


class ShippedShinyOddsTests(TestCase):
    def setUp(self):
        self.data = json.loads(catalog.SHINY_ODDS_FILE.read_text(encoding="utf-8"))
        self.methods = json.loads(
            catalog.SHINY_METHODS_FILE.read_text(encoding="utf-8")
        )["methods"]

    def test_file_is_well_formed(self):
        self.assertEqual(set(self.data), {"sources", "notes", "rules"})
        self.assertTrue(self.data["sources"])
        for rule in self.data["rules"]:
            with self.subTest(method=rule["method"], versions=rule["versions"]):
                self.assertIn(rule["kind"], catalog.SHINY_ODDS_KINDS)
                self.assertIn(rule["base"], catalog.SHINY_ODDS_BASES)
                self.assertTrue(rule["sources"])
                self.assertEqual(
                    rule["charmExceptForms"], sorted(set(rule["charmExceptForms"]))
                )

    def test_every_method_of_every_save_game_has_one_rule(self):
        # Nada pela metade: todo par método × jogo ligado ao HOME tem regra,
        # e uma só.
        expected = sorted(
            (m["id"], v)
            for m in self.methods
            for v in m["versions"]
            if v in HOME_ORIGIN_VERSIONS
        )
        pairs = sorted(
            (rule["method"], v) for rule in self.data["rules"] for v in rule["versions"]
        )
        self.assertEqual(pairs, expected)

    def test_some_known_odds(self):
        rules = {
            (rule["method"], v): rule
            for rule in self.data["rules"]
            for v in rule["versions"]
        }
        # Exemplos da curadoria (docs/roadmap/ideias/odds-das-cacadas.md).
        self.assertEqual(rules[("random", "brilliant-diamond")]["charm"], None)
        self.assertEqual(rules[("eggs", "sword")]["charm"], 1)
        self.assertEqual(rules[("masuda", "scarlet")]["rolls"], 6)
        self.assertEqual(rules[("random", "legends-arceus")]["charm"], 3)
        self.assertEqual(rules[("random", "firered")]["base"], 8192)
        self.assertIn("regidrago", rules[("soft-reset", "sword")]["charmExceptForms"])
        self.assertEqual(rules[("sos", "sun")]["chain"]["resetAfter"], 255)
        self.assertNotIn("resetAfter", rules[("sos", "ultra-sun")]["chain"])
        radar = rules[("poke-radar", "x")]["chain"]["steps"]
        self.assertEqual([radar[1]["odds"], radar[40]["odds"]], [7900, 100])
        self.assertEqual(
            rules[("chain-fishing", "omega-ruby")]["chain"]["steps"][-1],
            {"from": 20, "rolls": 40},
        )


class ShippedHomeCutoffsTests(TestCase):
    def test_bank_games_end_with_the_bank(self):
        data = json.loads(catalog.HOME_CUTOFFS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"sources", "notes", "cutoffs"})
        self.assertTrue(data["sources"])
        (bank,) = data["cutoffs"]
        self.assertEqual(bank["homeUntil"], "2027-02-26T03:00:00Z")
        self.assertEqual(
            set(bank["versions"]),
            set(HOME_ORIGIN_VERSIONS)
            - set(HOME_TRANSFER_VERSIONS)
            - {"firered", "leafgreen"},
        )


class ShippedSpecialEncountersTests(TestCase):
    def test_file_is_well_formed(self):
        data = json.loads(catalog.SPECIAL_ENCOUNTERS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"sources", "notes", "encounters"})
        for encounter in data["encounters"]:
            with self.subTest(name=encounter["name"]):
                self.assertEqual(
                    set(encounter),
                    {"name", "label", "versionGroup", "dlc", "species"},
                )
                self.assertIn(encounter["dlc"], (None, *catalog.DLC_VERSION_GROUPS))
                self.assertEqual(
                    len(encounter["species"]), len(set(encounter["species"]))
                )


class ShippedShinyLocksTests(TestCase):
    def test_file_is_well_formed(self):
        locks = json.loads(catalog.SHINY_LOCKS_FILE.read_text(encoding="utf-8"))
        captions = [lock["caption"] for lock in locks]
        self.assertEqual(len(captions), len(set(captions)))
        for lock in locks:
            with self.subTest(caption=lock["caption"]):
                self.assertEqual(
                    set(lock), {"caption", "description", "lockType", "active", "forms"}
                )
                self.assertIn(lock["lockType"], {"distro-only", "unobtainable"})
                self.assertTrue(lock["forms"])
