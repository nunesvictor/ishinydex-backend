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
            "sword": "swsh",
            "shield": "swsh",
            "brilliant-diamond": "bdsp",
            "shining-pearl": "bdsp",
            "scarlet": "sv",
            "violet": "sv",
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
