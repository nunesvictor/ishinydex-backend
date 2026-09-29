import os
import shutil
import subprocess
import tempfile
import time
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation

from psycopg2 import sql

from core.management.commands import backupdb, recreatedb, restoredb, sync_pokeapi
from core.services.pokeapi import PokeAPIClient
from core.tests import factories as f
from home.models import Box, PersonalDex, Slot
from pokedex.models import PokemonSpecies
from pokedex.tests.pokeapi_fixtures import FakePokeAPIClient


def run(command, *args, **kwargs):
    # StringIO não é um TTY: a saída sai sem cor, como em pipes e no cron.
    out = StringIO()
    call_command(command, *args, stdout=out, stderr=out, **kwargs)
    return out.getvalue()


class CommandOutputTests(TestCase):
    """Regressão: strings lazy no stdout quebravam os comandos sem TTY."""

    def test_commands_write_plain_text_without_tty(self):
        for command, args in (
            ("create_home_boxes", ["1"]),
            ("create_personal_dex", ["Main"]),
        ):
            with self.subTest(command=command):
                output = run(command, *args, no_color=True)

                self.assertNotIn("\x1b[", output)
                self.assertTrue(output.strip())

    def test_messages_are_translated(self):
        with translation.override("pt-br"):
            output = run("create_personal_dex", "Main")

        self.assertIn("Trabalhando no PersonalDex: `Main`", output)


class CreateHomeBoxesTests(TestCase):
    def test_creates_boxes_with_slots(self):
        run("create_home_boxes", "3")

        self.assertEqual(
            list(Box.objects.values_list("name", flat=True)),
            ["HOME 1", "HOME 2", "HOME 3"],
        )
        self.assertEqual(Slot.objects.count(), 90)

    def test_failure_rolls_back(self):
        f.make_box(name="HOME 2")

        with self.assertRaises(CommandError):
            run("create_home_boxes", "3")

        self.assertEqual(Box.objects.count(), 1)


class CreateHomeSchemeTests(TestCase):
    def setUp(self):
        self.boxes = [f.make_box(name=f"HOME {i}") for i in range(1, 4)]
        self.forms = [
            f.make_full_pokemon(name, i)[2]
            for i, name in enumerate(["bulbasaur", "ivysaur", "venusaur"], start=1)
        ]
        self.dex = f.make_personal_dex(*self.forms)

    def _scheme(self, *args, **kwargs):
        return run(
            "create_home_scheme",
            "-p",
            str(self.dex.pk),
            "-f",
            str(kwargs.pop("first_box", self.boxes[0]).pk),
            *args,
            **kwargs,
        )

    def _filled(self):
        return list(
            Slot.objects.filter(form__isnull=False)
            .order_by("box__position", "position")
            .values_list("box__name", "row", "col", "form__name", "personal_dex")
        )

    def test_installs_forms_in_order(self):
        self._scheme()

        self.assertEqual(
            self._filled(),
            [
                ("HOME 1", 0, 0, "bulbasaur", self.dex.pk),
                ("HOME 1", 0, 1, "ivysaur", self.dex.pk),
                ("HOME 1", 0, 2, "venusaur", self.dex.pk),
            ],
        )

    def test_starts_at_given_box(self):
        self._scheme(first_box=self.boxes[1])

        self.assertEqual({row[0] for row in self._filled()}, {"HOME 2"})

    def test_force_new_box_moves_generation_starter_to_next_box(self):
        _, _, chikorita = f.make_full_pokemon("chikorita", 152)
        self.dex.forms.add(chikorita)
        self.dex.force_new_box = True
        self.dex.save()

        self._scheme()

        self.assertIn(("HOME 2", 0, 0, "chikorita", self.dex.pk), self._filled())

    def test_without_force_new_box_keeps_filling_same_box(self):
        _, _, chikorita = f.make_full_pokemon("chikorita", 152)
        self.dex.forms.add(chikorita)

        self._scheme()

        self.assertIn(("HOME 1", 0, 3, "chikorita", self.dex.pk), self._filled())

    def test_not_enough_space(self):
        for i in range(30):
            self.dex.forms.add(f.make_full_pokemon(f"extra-{i}", 1000 + i)[2])

        with self.assertRaises(CommandError):
            self._scheme("-l", str(self.boxes[0].pk))

        self.assertEqual(self._filled(), [])

    def test_unknown_personal_dex(self):
        with self.assertRaises(CommandError):
            run("create_home_scheme", "-p", "999999", "-f", str(self.boxes[0].pk))

    def test_empty_dex_warns(self):
        self.dex.forms.clear()

        output = self._scheme()

        self.assertIn("No forms to install", output)

    def _occupy_last_slot(self):
        slot = self.boxes[0].slots.last()
        slot.form = self.forms[0]
        slot.specimen = f.make_specimen(self.forms[0])
        slot.save()
        return slot

    @mock.patch("builtins.input", return_value="y")
    def test_clear_keeps_specimens(self, _input):
        slot = self._occupy_last_slot()

        self._scheme("--clear")

        slot.refresh_from_db()
        self.assertIsNone(slot.form)
        self.assertIsNotNone(slot.specimen)

    @mock.patch("builtins.input", return_value="y")
    def test_prune_removes_specimens(self, _input):
        slot = self._occupy_last_slot()

        self._scheme("--prune")

        slot.refresh_from_db()
        self.assertIsNone(slot.form)
        self.assertIsNone(slot.specimen)

    @mock.patch("builtins.input", return_value="n")
    def test_clear_aborted_by_user(self, _input):
        slot = self._occupy_last_slot()

        with self.assertRaises(CommandError):
            self._scheme("--clear")

        slot.refresh_from_db()
        self.assertEqual(slot.form, self.forms[0])


class CreatePersonalDexTests(TestCase):
    def setUp(self):
        _, self.pikachu, self.pikachu_form = f.make_full_pokemon("pikachu", 25)
        self.pikachu_cap = f.make_form(self.pikachu, name="pikachu-original-cap")
        _, arceus, _ = f.make_full_pokemon("arceus", 493)
        self.arceus_fire = f.make_form(arceus, name="arceus-fire", is_default=False)
        _, venusaur, self.venusaur = f.make_full_pokemon("venusaur", 3)
        self.mega = f.make_form(
            venusaur, name="venusaur-mega", is_default=False, is_battle_only=True
        )
        _, alcremie, _ = f.make_full_pokemon("alcremie", 869)
        self.alcremie_vanilla = f.make_form(
            alcremie, name="alcremie-vanilla-cream-strawberry"
        )
        self.alcremie_ruby = f.make_form(alcremie, name="alcremie-ruby-cream")

    def test_creates_dex_with_default_exclusions(self):
        with translation.override("en"):
            output = run("create_personal_dex", "Main", "-s", "-f")

        dex = PersonalDex.objects.get(name="Main")
        names = set(dex.forms.values_list("name", flat=True))
        self.assertTrue(dex.is_shiny_dex)
        self.assertTrue(dex.force_new_box)
        self.assertIn("created", output)
        self.assertLessEqual(
            {"pikachu", "venusaur", "arceus", "alcremie-vanilla-cream-strawberry"},
            names,
        )
        self.assertTrue(
            names.isdisjoint(
                {
                    "pikachu-original-cap",
                    "arceus-fire",
                    "venusaur-mega",
                    "alcremie",
                    "alcremie-ruby-cream",
                }
            )
        )

    def test_updates_existing_dex(self):
        dex = f.make_personal_dex(self.mega, name="Main", is_shiny_dex=True)

        with translation.override("en"):
            output = run("create_personal_dex", "Main")

        dex.refresh_from_db()
        self.assertFalse(dex.is_shiny_dex)
        self.assertFalse(dex.forms.filter(pk=self.mega.pk).exists())
        self.assertIn("updated", output)

    @mock.patch("builtins.input", return_value="y")
    def test_install_scheme_uses_existing_boxes(self, _input):
        f.make_box(name="HOME 1")

        run("create_personal_dex", "Main", "-i")

        dex = PersonalDex.objects.get(name="Main")
        self.assertEqual(
            Slot.objects.filter(personal_dex=dex).count(), dex.forms.count()
        )

    @mock.patch("builtins.input", return_value="y")
    def test_install_scheme_creates_boxes_when_missing(self, _input):
        run("create_personal_dex", "Main", "-i")

        self.assertEqual(Box.objects.count(), 200)
        self.assertTrue(Slot.objects.filter(personal_dex__name="Main").exists())

    @mock.patch("builtins.input", return_value="n")
    def test_install_scheme_aborted_without_boxes(self, _input):
        with self.assertRaises(CommandError):
            run("create_personal_dex", "Main", "-i")

        self.assertFalse(PersonalDex.objects.exists())


class SyncPokeAPICommandTests(TestCase):
    def setUp(self):
        self.fake = FakePokeAPIClient()
        patcher = mock.patch(
            "core.management.commands.sync_pokeapi.Command.get_client",
            return_value=self.fake,
        )
        self.get_client = patcher.start()
        self.addCleanup(patcher.stop)

    def test_full_sync(self):
        with translation.override("en"):
            output = run("sync_pokeapi")

        self.assertIn("species=3", output)
        self.assertIn("pokemon=4", output)
        self.assertEqual(PokemonSpecies.objects.count(), 3)

    def test_options_are_passed_to_client(self):
        run("sync_pokeapi", "pikachu", "--refresh", "--workers", "3")

        options = self.get_client.call_args.kwargs
        self.assertTrue(options["refresh"])
        self.assertEqual(options["workers"], 3)
        self.assertEqual(
            list(PokemonSpecies.objects.values_list("name", flat=True)), ["pikachu"]
        )

    def test_unknown_species(self):
        with self.assertRaisesMessage(CommandError, "missingno"):
            run("sync_pokeapi", "missingno")


class SyncPokeAPIGetClientTests(SimpleTestCase):
    def test_builds_client_from_options(self):
        client = sync_pokeapi.Command().get_client(refresh=True, workers=3)

        self.assertIsInstance(client, PokeAPIClient)
        self.assertTrue(client.refresh)
        self.assertEqual(client.max_workers, 3)


class LinkSpecimensTests(TestCase):
    def setUp(self):
        _, _, self.form = f.make_full_pokemon("bulbasaur", 1)
        _, _, self.other_form = f.make_full_pokemon("ivysaur", 2)
        self.box = f.make_box()
        self.dex = f.make_personal_dex(self.form, name="Shiny", is_shiny_dex=True)
        self.slot = self._scheme_slot(0, self.form, self.dex)

    def _scheme_slot(self, col, form, dex):
        slot = self.box.slots.get(row=0, col=col)
        slot.form, slot.personal_dex = form, dex
        slot.save()
        return slot

    def test_prefers_specimen_matching_dex_shininess(self):
        f.make_specimen(self.form, is_shiny=False)
        shiny = f.make_specimen(self.form, is_shiny=True)

        run("link_specimens")

        self.slot.refresh_from_db()
        self.assertEqual(self.slot.specimen, shiny)

    def test_falls_back_to_other_shininess(self):
        regular = f.make_specimen(self.form, is_shiny=False)

        run("link_specimens")

        self.slot.refresh_from_db()
        self.assertEqual(self.slot.specimen, regular)

    def test_strict_does_not_fall_back(self):
        f.make_specimen(self.form, is_shiny=False)

        output = run("link_specimens", "--strict")

        self.slot.refresh_from_db()
        self.assertIsNone(self.slot.specimen)
        self.assertIn("1", output)

    def test_never_reuses_deposited_specimens(self):
        specimen = f.make_specimen(self.form, is_shiny=True)
        second = self._scheme_slot(1, self.form, self.dex)

        run("link_specimens")

        self.slot.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.slot.specimen, specimen)
        self.assertIsNone(second.specimen)

        run("link_specimens")

        second.refresh_from_db()
        self.assertIsNone(second.specimen)

    def test_only_given_dex(self):
        other_dex = f.make_personal_dex(self.other_form, name="Regular")
        other_slot = self._scheme_slot(1, self.other_form, other_dex)
        f.make_specimen(self.form, is_shiny=True)
        f.make_specimen(self.other_form)

        run("link_specimens", "Regular")

        self.slot.refresh_from_db()
        other_slot.refresh_from_db()
        self.assertIsNone(self.slot.specimen)
        self.assertIsNotNone(other_slot.specimen)

    def test_dex_by_id_and_unknown(self):
        f.make_specimen(self.form, is_shiny=True)

        run("link_specimens", str(self.dex.pk))
        self.slot.refresh_from_db()
        self.assertIsNotNone(self.slot.specimen)

        with self.assertRaises(CommandError):
            run("link_specimens", "nope")

    def test_dry_run_does_not_save(self):
        f.make_specimen(self.form, is_shiny=True)

        output = run("link_specimens", "--dry-run")

        self.slot.refresh_from_db()
        self.assertIsNone(self.slot.specimen)
        self.assertIn("bulbasaur", output)

    def test_query_count_does_not_grow_with_slots(self):
        for col in range(1, 6):
            self._scheme_slot(col, self.form, self.dex)
        for _ in range(6):
            f.make_specimen(self.form, is_shiny=True)

        # savepoint, dexes, slots, specimens, bulk update, release
        with self.assertNumQueries(6):
            run("link_specimens", str(self.dex.pk))

        self.assertEqual(
            Slot.objects.filter(personal_dex=self.dex, specimen__isnull=False).count(),
            6,
        )


class RecreateDbTests(SimpleTestCase):
    @mock.patch.object(recreatedb, "call_command")
    @mock.patch.object(recreatedb, "connections")
    def test_quotes_database_name_and_forces_drop(self, connections_mock, cmd_mock):
        default = connections_mock.__getitem__.return_value
        cursor = default.Database.connect.return_value.cursor.return_value

        with mock.patch.dict(settings.DATABASES["default"], NAME="ishinydex-dev"):
            run("recreatedb")

        default.close.assert_called_once()
        self.assertEqual(
            default.Database.connect.call_args.kwargs["dbname"], "postgres"
        )
        name = sql.Identifier("ishinydex-dev")
        self.assertEqual(
            [c.args[0] for c in cursor.execute.call_args_list],
            [
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE);").format(name),
                sql.SQL("CREATE DATABASE {};").format(name),
            ],
        )
        self.assertEqual(
            [c.args[0] for c in cmd_mock.call_args_list], ["migrate", "createsuperuser"]
        )


DB_SETTINGS = {
    "NAME": "ishinydex",
    "USER": "pokeuser",
    "PASSWORD": "secret",
    "HOST": "db",
    "PORT": 5432,
}


class BackupTestCase(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        db_patch = mock.patch.dict(settings.DATABASES["default"], DB_SETTINGS)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        backups_dir = override_settings(BACKUPS_DIR=self.tmp)
        backups_dir.enable()
        self.addCleanup(backups_dir.disable)

    def assert_connection_args(self, run_mock):
        cmd = run_mock.call_args.args[0]
        for flag, value in (
            ("-h", "db"),
            ("-p", "5432"),
            ("-U", "pokeuser"),
            ("-d", "ishinydex"),
        ):
            self.assertEqual(cmd[cmd.index(flag) + 1], value)
        self.assertEqual(run_mock.call_args.kwargs["env"]["PGPASSWORD"], "secret")


@mock.patch.object(backupdb, "call_command")
@mock.patch.object(backupdb.subprocess, "run")
class BackupDbTests(BackupTestCase):
    def test_runs_pg_dump_with_settings_connection(self, run_mock, clearsessions):
        run_mock.return_value = subprocess.CompletedProcess([], 0, "", "")

        output = run("backupdb")

        clearsessions.assert_called_once_with("clearsessions")
        cmd = run_mock.call_args.args[0]
        self.assertEqual(cmd[0], "pg_dump")
        self.assertIn("-Fc", cmd)
        self.assert_connection_args(run_mock)
        backup_file = Path(cmd[cmd.index("-f") + 1])
        self.assertEqual(backup_file.parent, self.tmp)
        self.assertRegex(backup_file.name, r"^dump-ishinydex-\d{12}\.backup$")
        self.assertIn("dumped to", output)

    def test_timestamp_is_computed_on_each_run(self, run_mock, _clearsessions):
        run_mock.return_value = subprocess.CompletedProcess([], 0, "", "")

        for minute in ("202609281200", "202609281201"):
            with mock.patch.object(backupdb, "datetime") as dt_mock:
                dt_mock.now.return_value.strftime.return_value = minute
                run("backupdb")

        names = [Path(c.args[0][-1]).name for c in run_mock.call_args_list]
        self.assertEqual(
            names,
            [
                "dump-ishinydex-202609281200.backup",
                "dump-ishinydex-202609281201.backup",
            ],
        )

    def test_reports_failure(self, run_mock, _clearsessions):
        run_mock.return_value = subprocess.CompletedProcess([], 1, "", "boom")

        output = run("backupdb")

        self.assertIn("Failed to dump", output)
        self.assertIn("boom", output)

    def test_pg_dump_not_installed(self, run_mock, _clearsessions):
        run_mock.side_effect = FileNotFoundError

        self.assertIn("'pg_dump' not found", run("backupdb"))


@mock.patch.object(restoredb.subprocess, "run")
class RestoreDbTests(BackupTestCase):
    def _backup(self, name, age):
        path = self.tmp / name
        path.touch()
        mtime = time.time() - age
        os.utime(path, (mtime, mtime))
        return path

    def test_no_backups(self, run_mock):
        output = run("restoredb")

        run_mock.assert_not_called()
        self.assertIn("No .backup files", output)

    def test_restores_newest_backup(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess([], 0, "", "")
        self._backup("old.backup", age=3600)
        newest = self._backup("new.backup", age=10)
        self._backup("ignored.sql", age=0)

        output = run("restoredb")

        cmd = run_mock.call_args.args[0]
        self.assertEqual(cmd[0], "pg_restore")
        self.assertEqual(cmd[-1], str(newest))
        self.assertIn("--if-exists", cmd)
        self.assert_connection_args(run_mock)
        self.assertIn("successfully restored", output)

    def test_reports_failure(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess([], 1, "", "boom")
        self._backup("a.backup", age=0)

        self.assertIn("Failed to restore", run("restoredb"))

    def test_pg_restore_not_installed(self, run_mock):
        run_mock.side_effect = FileNotFoundError
        self._backup("a.backup", age=0)

        self.assertIn("'pg_restore' not found", run("restoredb"))
