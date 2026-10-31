import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from core.management.commands import sync_held_items
from core.services.pokeapi import PokeAPIClient
from core.tests import factories as f
from pokedex import held_items
from pokedex.held_items import HeldItemsError, HeldItemsImporter, item_slug
from pokedex.models import HeldItem
from pokedex.showdown import ShowdownItems
from pokedex.tests.showdown_fixtures import showdown_tree

POKEAPI_ITEMS = ["ability-shield", "leftovers", "kings-rock", "firium-z--held", "stick"]


class FakeItemsClient:
    def __init__(self, names=POKEAPI_ITEMS):
        self.names = names

    def list(self, endpoint):
        assert endpoint == "item"
        return [{"name": n, "url": f"item/{n}/"} for n in self.names]


class ItemSlugTests(SimpleTestCase):
    def test_slug(self):
        self.assertEqual(item_slug("King's Rock"), "kings-rock")
        self.assertEqual(item_slug("PRZ Cure Berry"), "prz-cure-berry")
        self.assertEqual(item_slug("Flabébé"), "flabebe")


class HeldItemsImporterTests(TestCase):
    def setUp(self):
        self.tmp = showdown_tree()
        self.addCleanup(self.tmp.cleanup)
        self.sv = f.make_version_group(name="scarlet-violet", order=25)
        self.bdsp = f.make_version_group(
            name="brilliant-diamond-shining-pearl", order=23
        )
        self.gs = f.make_version_group(name="gold-silver", order=3)
        self.lgpe = f.make_version_group(name="lets-go-pikachu-lets-go-eevee", order=19)
        self.data = {
            "versionGroups": {
                "scarlet-violet": "base",
                "brilliant-diamond-shining-pearl": "gen8bdsp",
                "gold-silver": "gen2",
                "lets-go-pikachu-lets-go-eevee": None,
                # Grupo que o banco não tem (import parcial): fica de fora.
                "champions": "gen8",
            },
            "curated": {},
            "aliases": {"Leek": "stick"},
            "withoutSprite": ["Berserk Gene"],
        }

    def run_import(self, client=None):
        file = Path(self.tmp.name) / "held_items.json"
        file.write_text(json.dumps(self.data), encoding="utf-8")
        with mock.patch.object(held_items, "HELD_ITEMS_FILE", file):
            return HeldItemsImporter(
                client or FakeItemsClient(),  # type: ignore[arg-type]
                ShowdownItems(self.tmp.name),
                log=lambda _: None,
            ).run()

    def groups(self, name):
        return sorted(
            HeldItem.objects.get(name=name).version_groups.values_list(
                "name", flat=True
            )
        )

    def test_imports_items_by_version_group(self):
        self.assertEqual(self.run_import(), 6)

        self.assertEqual(
            self.groups("leftovers"),
            ["brilliant-diamond-shining-pearl", "gold-silver", "scarlet-violet"],
        )
        self.assertEqual(self.groups("ability-shield"), ["scarlet-violet"])
        self.assertEqual(self.groups("kings-rock"), ["gold-silver", "scarlet-violet"])
        self.assertFalse(HeldItem.objects.filter(version_groups=self.lgpe).exists())

    def test_names_from_pokeapi(self):
        self.run_import()

        # O alias, o "--held" dos Z-Crystals e o rótulo do Showdown.
        leek = HeldItem.objects.get(name="stick")
        self.assertEqual((leek.label, leek.has_sprite), ("Leek", True))
        self.assertEqual(HeldItem.objects.get(name="firium-z--held").label, "Firium Z")
        self.assertEqual(HeldItem.objects.get(name="kings-rock").label, "King's Rock")

    def test_item_without_pokeapi_pair_listed_comes_without_sprite(self):
        self.run_import()

        gene = HeldItem.objects.get(name="berserk-gene")
        self.assertFalse(gene.has_sprite)
        self.assertEqual(self.groups("berserk-gene"), ["gold-silver"])

    def test_curated_list_instead_of_a_showdown_mod(self):
        za = f.make_version_group(name="legends-za", order=30)
        self.data["versionGroups"]["legends-za"] = "legends-za"
        self.data["curated"] = {"legends-za": ["Leftovers", "Leek"]}

        self.assertEqual(self.run_import(), 6)
        self.assertEqual(
            sorted(
                HeldItem.objects.filter(version_groups=za).values_list(
                    "name", flat=True
                )
            ),
            ["leftovers", "stick"],
        )

    def test_curated_item_without_pokeapi_pair_fails(self):
        f.make_version_group(name="legends-za", order=30)
        self.data["versionGroups"]["legends-za"] = "legends-za"
        self.data["curated"] = {"legends-za": ["Made Up Orb"]}

        with self.assertRaisesMessage(
            HeldItemsError, "sem par na PokéAPI: Made Up Orb"
        ):
            self.run_import()

    def test_item_without_pokeapi_pair_fails(self):
        with self.assertRaisesMessage(HeldItemsError, "sem par na PokéAPI: Leftovers"):
            self.run_import(FakeItemsClient(["ability-shield", "kings-rock"]))

    def test_version_group_without_mod_fails(self):
        f.make_version_group(name="legends-zz")

        with self.assertRaisesMessage(
            HeldItemsError, "sem mod do Showdown: ['legends-zz']"
        ):
            self.run_import()

    def test_unknown_mod_fails(self):
        self.data["versionGroups"]["scarlet-violet"] = "gen9zz"

        with self.assertRaisesMessage(HeldItemsError, "desconhecido: gen9zz"):
            self.run_import()

    def test_runs_again_without_duplicates_and_drops_old_items(self):
        self.run_import()
        HeldItem.objects.create(name="old-item", label="Old Item")
        self.data["versionGroups"]["gold-silver"] = None

        self.assertEqual(self.run_import(), 5)
        self.assertFalse(HeldItem.objects.filter(name="old-item").exists())
        self.assertFalse(HeldItem.objects.filter(name="berserk-gene").exists())
        self.assertEqual(
            self.groups("leftovers"),
            ["brilliant-diamond-shining-pearl", "scarlet-violet"],
        )


class ShippedHeldItemsTests(SimpleTestCase):
    def test_file_is_well_formed(self):
        data = json.loads(held_items.HELD_ITEMS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(
            set(data),
            {
                "sources",
                "notes",
                "versionGroups",
                "curated",
                "aliases",
                "withoutSprite",
            },
        )
        for name, labels in data["curated"].items():
            with self.subTest(curated=name):
                self.assertEqual(labels, sorted(set(labels)))
                self.assertIn(name, data["versionGroups"].values())
        self.assertTrue(data["sources"])
        for group, mod in data["versionGroups"].items():
            with self.subTest(group=group):
                self.assertTrue(mod is None or isinstance(mod, str))
        self.assertEqual(data["withoutSprite"], sorted(set(data["withoutSprite"])))


class SyncHeldItemsCommandTests(TestCase):
    def setUp(self):
        self.tmp = showdown_tree()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch(
            "core.management.commands.sync_held_items.Command.get_client",
            return_value=FakeItemsClient(),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.data = Path(self.tmp.name) / "held_items.json"
        self.data.write_text(
            json.dumps(
                {
                    "versionGroups": {"scarlet-violet": "base"},
                    "curated": {},
                    "aliases": {"Leek": "stick"},
                    "withoutSprite": [],
                }
            ),
            encoding="utf-8",
        )
        patcher = mock.patch.object(held_items, "HELD_ITEMS_FILE", self.data)
        patcher.start()
        self.addCleanup(patcher.stop)
        f.make_version_group(name="scarlet-violet")

    def test_imports(self):
        out = StringIO()
        call_command("sync_held_items", self.tmp.name, stdout=out)

        self.assertIn("held_items=4", out.getvalue())
        self.assertEqual(HeldItem.objects.count(), 4)

    def test_errors_become_command_errors(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesMessage(CommandError, "items.ts não existe"):
                call_command("sync_held_items", empty, stdout=StringIO())

        f.make_version_group(name="new-game")
        with self.assertRaisesMessage(CommandError, "sem mod do Showdown"):
            call_command("sync_held_items", self.tmp.name, stdout=StringIO())


class SyncHeldItemsGetClientTests(SimpleTestCase):
    def test_get_client(self):
        self.assertIsInstance(sync_held_items.Command().get_client(), PokeAPIClient)
