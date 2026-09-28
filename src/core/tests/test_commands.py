import os
import subprocess
import tempfile
import time
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from psycopg2 import sql

from core.management.commands import backupdb, recreatedb, restoredb
from core.tests import factories as f
from home.models import Box, PersonalDex, Slot


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


class RecreateDbTests(SimpleTestCase):
    @mock.patch.object(recreatedb, "call_command")
    @mock.patch.object(recreatedb, "connections")
    def test_quotes_database_name_and_forces_drop(self, connections_mock, cmd_mock):
        default = connections_mock.__getitem__.return_value
        cursor = default.Database.connect.return_value.cursor.return_value

        with mock.patch.dict(settings.DATABASES["default"], NAME="django-pokedex"):
            run("recreatedb")

        default.close.assert_called_once()
        self.assertEqual(
            default.Database.connect.call_args.kwargs["dbname"], "postgres"
        )
        name = sql.Identifier("django-pokedex")
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


class BackupDbTests(TestCase):
    @mock.patch.object(backupdb, "call_command")
    @mock.patch.object(backupdb.subprocess, "run")
    def test_runs_pg_dump(self, run_mock, clearsessions_mock):
        run_mock.return_value = subprocess.CompletedProcess([], 0, "", "")

        output = run("backupdb")

        clearsessions_mock.assert_called_once_with("clearsessions")
        cmd = run_mock.call_args.args[0]
        self.assertEqual(cmd[0], "pg_dump")
        self.assertIn("-Fc", cmd)
        self.assertEqual(cmd[cmd.index("-f") + 1], backupdb.backup_filename)
        self.assertEqual(
            run_mock.call_args.kwargs["env"]["PGPASSWORD"], backupdb.POSTGRES_PASSWORD
        )
        self.assertIn("dumped to", output)

    @mock.patch.object(backupdb, "call_command")
    @mock.patch.object(backupdb.subprocess, "run")
    def test_reports_failure(self, run_mock, _clearsessions):
        run_mock.return_value = subprocess.CompletedProcess([], 1, "", "boom")

        output = run("backupdb")

        self.assertIn("Failed to dump", output)
        self.assertIn("boom", output)

    @mock.patch.object(backupdb, "call_command")
    @mock.patch.object(backupdb.subprocess, "run", side_effect=FileNotFoundError)
    def test_pg_dump_not_installed(self, _run, _clearsessions):
        self.assertIn("'pg_dump' not found", run("backupdb"))


class RestoreDbTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(restoredb, "BACKUPS_DIR", self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _backup(self, name, age):
        path = Path(self.tmp.name) / name
        path.touch()
        mtime = time.time() - age
        os.utime(path, (mtime, mtime))
        return path

    def test_no_backups(self):
        with mock.patch.object(restoredb.subprocess, "run") as run_mock:
            output = run("restoredb")

        run_mock.assert_not_called()
        self.assertIn("No .backup files", output)

    @mock.patch.object(restoredb.subprocess, "run")
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
        self.assertIn("successfully restored", output)

    @mock.patch.object(restoredb.subprocess, "run")
    def test_reports_failure(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess([], 1, "", "boom")
        self._backup("a.backup", age=0)

        self.assertIn("Failed to restore", run("restoredb"))
