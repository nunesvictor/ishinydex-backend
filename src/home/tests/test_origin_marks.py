from importlib import import_module

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from core.tests import factories as f
from home.models import Specimen
from home.origin_marks import (
    ORIGIN_MARK_LABELS,
    ORIGIN_MARK_VERSION_GROUPS,
    origin_mark_for,
    origin_mark_options,
)


class OriginMarkForTests(SimpleTestCase):
    def test_every_version_group_maps_to_its_mark(self):
        for mark, groups in ORIGIN_MARK_VERSION_GROUPS.items():
            for group in groups:
                with self.subTest(group=group):
                    self.assertEqual(origin_mark_for(group, False), mark)

    def test_dlcs_use_the_base_game_mark(self):
        self.assertEqual(origin_mark_for("the-indigo-disk", False), "paldea")
        self.assertEqual(origin_mark_for("the-crown-tundra", False), "galar")
        self.assertEqual(origin_mark_for("mega-dimension", False), "lumiose")

    def test_frlg_has_the_game_boy_advance_mark(self):
        # FRLG do Switch (HOME 4.1.0); os outros jogos da Gen III, não.
        self.assertEqual(origin_mark_for("firered-leafgreen", False), "gba")
        self.assertEqual(ORIGIN_MARK_LABELS["gba"], "GBA")
        self.assertIsNone(origin_mark_for("ruby-sapphire", False))

    def test_games_without_mark(self):
        for group in ("emerald", "black-2-white-2", "xd", "champions", "", None):
            with self.subTest(group=group):
                self.assertIsNone(origin_mark_for(group, False))

    def test_go_has_priority(self):
        self.assertEqual(origin_mark_for("scarlet-violet", True), "go")
        self.assertEqual(origin_mark_for(None, True), "go")

    def test_options_have_every_mark_go_and_none(self):
        options = origin_mark_options()

        self.assertEqual([o["value"] for o in options], list(ORIGIN_MARK_LABELS))
        self.assertEqual(
            [o["value"] for o in options][-2:],
            ["go", "none"],
        )
        self.assertEqual(options[-1]["label"], "Sem marca de origem")
        # Siglas dos jogos, sem tradução.
        labels = {o["value"]: o["label"] for o in options}
        self.assertEqual(labels["alola"], "SM/USUM")
        self.assertEqual(labels["kalos"], "XY/ORAS")
        self.assertEqual(labels["bdsp"], "BDSP")
        self.assertEqual(labels["galar"], "SwSh")


class FillOriginVersionMigrationTests(TestCase):
    def test_fills_existing_specimens_from_ot(self):
        migration = import_module("home.migrations.0004_fill_specimen_origin_version")
        _, _, form = f.make_full_pokemon("bulbasaur", 1)
        red = f.make_version(name="red")
        with_version = f.make_specimen(form, ot=f.make_ot(version=red))
        without_version = f.make_specimen(form, ot=f.make_ot(trainer_id="2"))
        without_ot = f.make_specimen(form)
        Specimen.objects.update(origin_version=None)

        migration.fill_origin_version(apps, None)

        self.assertEqual(
            dict(Specimen.objects.values_list("pk", "origin_version")),
            {with_version.pk: red.pk, without_version.pk: None, without_ot.pk: None},
        )
