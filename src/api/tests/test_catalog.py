import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from api import catalog
from core.tests import factories as f
from pokedex.models import PokemonAbility


class CatalogTests(TestCase):
    """Pacote do catálogo (``build_catalog`` e ``exportcatalog``)."""

    @classmethod
    def setUpTestData(cls):
        sv = f.make_version_group(
            name="scarlet-violet", generation="generation-ix", versions=["scarlet"]
        )
        f.make_version(name="scarlet", version_group=sv)
        f.make_version(name="yellow")
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
