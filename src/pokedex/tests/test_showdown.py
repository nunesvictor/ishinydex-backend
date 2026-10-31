import tempfile

from django.test import SimpleTestCase

from pokedex.showdown import (
    ShowdownError,
    ShowdownItems,
    parse_items,
    parse_learnsets,
    read_learnsets,
)
from pokedex.tests.showdown_fixtures import ITEMS, LEARNSETS, showdown_tree


class ParseItemsTests(SimpleTestCase):
    def test_reads_only_the_simple_fields(self):
        items = parse_items(ITEMS)

        self.assertEqual(items["abilityshield"], {"name": "Ability Shield", "gen": 9})
        self.assertEqual(items["firiumz"]["isNonstandard"], "Past")
        self.assertIs(items["pokeball"]["isPokeball"], True)
        self.assertEqual(len(items), 7)


class ShowdownItemsTests(SimpleTestCase):
    def setUp(self):
        self.tmp = showdown_tree()
        self.addCleanup(self.tmp.cleanup)
        self.showdown = ShowdownItems(self.tmp.name)

    def names(self, mod):
        return sorted(self.showdown.held_items(mod).values())

    def test_base_is_the_current_generation(self):
        # Sem os "Past" (Firium Z, Berserk Gene) e sem a pokébola.
        self.assertEqual(
            self.names("base"), ["Ability Shield", "King's Rock", "Leek", "Leftovers"]
        )

    def test_mod_overrides_and_filters_by_generation(self):
        # O gen8 herda da base, traz o Firium Z de volta e tira o da 9ª.
        self.assertEqual(
            self.names("gen8"), ["Firium Z", "King's Rock", "Leek", "Leftovers"]
        )

    def test_mod_with_inherit_in_scripts(self):
        self.assertEqual(self.names("gen8bdsp"), ["Firium Z", "Leek", "Leftovers"])

    def test_mod_with_only_inherit_takes_the_parent_generation(self):
        self.assertEqual(self.names("gen4pt"), ["King's Rock", "Leftovers"])

    def test_old_generation_inherits_through_the_newer_ones(self):
        # O gen2 redefine o Leek (gen 2) e traz o Berserk Gene.
        self.assertEqual(
            self.names("gen2"), ["Berserk Gene", "King's Rock", "Leek", "Leftovers"]
        )

    def test_ids(self):
        self.assertEqual(
            set(self.showdown.held_items("gen8bdsp")), {"firiumz", "leek", "leftovers"}
        )

    def test_mod_without_items_fails(self):
        with self.assertRaisesMessage(ShowdownError, "nenhum item"):
            self.showdown.held_items("gen1")

    def test_unknown_mod_fails(self):
        with self.assertRaisesMessage(ShowdownError, "desconhecido: gen9legends"):
            self.showdown.held_items("gen9legends")

    def test_mod_without_generation_fails(self):
        tmp = showdown_tree(**{"mods/custom/scripts.ts": "export const S = {};\n"})
        self.addCleanup(tmp.cleanup)

        with self.assertRaisesMessage(ShowdownError, "sem geração: custom"):
            ShowdownItems(tmp.name).held_items("custom")

    def test_clone_without_items_fails(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesMessage(ShowdownError, "items.ts não existe"):
                ShowdownItems(empty)


class LearnsetsTests(SimpleTestCase):
    def test_reads_the_learnset_of_each_form(self):
        learnsets = parse_learnsets(LEARNSETS)

        self.assertEqual(
            learnsets["pumpkaboo"], {"astonish": ["9L1"], "shadowball": ["9M", "9L30"]}
        )
        self.assertEqual(learnsets["floetteeternal"], {"lightofruin": ["9L50", "9S0"]})
        # Só com eventData: sem learnset.
        self.assertNotIn("mewtwo", learnsets)
        self.assertEqual(len(learnsets), 5)

    def test_reads_the_file_of_a_mod(self):
        tmp = showdown_tree(**{"mods/gen9legends/learnsets.ts": LEARNSETS})
        self.addCleanup(tmp.cleanup)

        self.assertEqual(
            read_learnsets(tmp.name, "gen9legends"), parse_learnsets(LEARNSETS)
        )

    def test_missing_or_empty_file_fails(self):
        tmp = showdown_tree(**{"mods/gen9empty/learnsets.ts": "export const L = {};\n"})
        self.addCleanup(tmp.cleanup)

        with self.assertRaisesMessage(
            ShowdownError, "gen9legends/learnsets.ts não existe"
        ):
            read_learnsets(tmp.name, "gen9legends")
        with self.assertRaisesMessage(
            ShowdownError, "nenhum golpe no mod do Showdown gen9empty"
        ):
            read_learnsets(tmp.name, "gen9empty")
