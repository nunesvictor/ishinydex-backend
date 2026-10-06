import json
import shutil
import tempfile
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.tests import factories as f
from home.models import Save, Slot
from home.userdata import build_user_data


class UserDataTests(TestCase):
    """Os dados do usuário no formato do app local (``exportuserdata``)."""

    @classmethod
    def setUpTestData(cls):
        scarlet = f.make_version(name="scarlet")
        _, _, cls.bulba = f.make_full_pokemon("bulbasaur", 1)
        # Id do banco diferente do da PokéAPI: o arquivo usa o da PokéAPI.
        _, _, cls.mew = f.make_full_pokemon("mew", 151)
        cls.ot = f.make_ot(name="Ash", trainer_id="123456", version=scarlet)
        cls.other_ot = f.make_ot(name="Misty")
        cls.save = Save.objects.create(trainer=cls.ot, label="Switch")
        cls.dex = f.make_personal_dex(cls.bulba, cls.mew, is_shiny_dex=True)
        cls.box = f.make_box(name="HOME 1")
        cls.lock = f.make_shinylock(
            cls.mew, caption="Mew", lock_type="distro-only", description=None
        )
        cls.specimen = f.make_specimen(
            cls.bulba,
            nickname="Bulba",
            is_shiny=True,
            ot=cls.ot,
            captured_at=date(2024, 9, 23),
            pokeball="poke-ball",
            location=cls.save,
            location_since=date(2026, 3, 12),
        )
        # A box nasce com os slots vazios; três deles ganham dex e forma.
        Slot.objects.filter(box=cls.box, row=0, col=0).update(
            personal_dex=cls.dex, form=cls.bulba, specimen=cls.specimen
        )
        Slot.objects.filter(box=cls.box, row=0, col=1).update(
            personal_dex=cls.dex, form=cls.mew
        )
        cls.slots = Slot.objects.filter(box=cls.box).count()

    def test_envelope(self):
        now = datetime(2026, 10, 6, 12, 30, 15, 123456, tzinfo=timezone.utc)
        data = build_user_data("catalog-2026.10.03", now=now)
        self.assertEqual(data["schemaVersion"], 1)
        self.assertEqual(data["kind"], "ishinydex-data")
        self.assertEqual(data["catalog"], "catalog-2026.10.03")
        self.assertEqual(data["savedAt"], "2026-10-06T12:30:15.123Z")
        self.assertEqual(data["deleted"], {})
        self.assertEqual(
            list(data["records"]),
            ["trainers", "saves", "dexes", "boxes", "shinyLocks", "specimens", "slots"],
        )

    def test_records(self):
        records = build_user_data("")["records"]
        updated = {r["updatedAt"] for records_ in records.values() for r in records_}
        for stamp in updated:
            self.assertRegex(stamp, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

        def strip(record):
            return {k: v for k, v in record.items() if k != "updatedAt"}

        self.assertEqual(
            [strip(t) for t in records["trainers"]],
            [
                {
                    "id": self.ot.pk,
                    "name": "Ash",
                    "trainerId": "123456",
                    "version": "scarlet",
                },
                {
                    "id": self.other_ot.pk,
                    "name": "Misty",
                    "trainerId": self.other_ot.trainer_id,
                    "version": None,
                },
            ],
        )
        self.assertEqual(
            [strip(s) for s in records["saves"]],
            [{"id": self.save.pk, "trainer": self.ot.pk, "label": "Switch"}],
        )
        self.assertEqual(
            [strip(d) for d in records["dexes"]],
            [
                {
                    "id": self.dex.pk,
                    "name": self.dex.name,
                    "isShinyDex": True,
                    "forceNewBox": False,
                }
            ],
        )
        self.assertEqual(
            [strip(b) for b in records["boxes"]],
            [{"id": self.box.pk, "name": "HOME 1", "position": self.box.position}],
        )
        self.assertEqual(
            [strip(lock) for lock in records["shinyLocks"]],
            [
                {
                    "id": self.lock.pk,
                    "caption": "Mew",
                    "description": None,
                    "lockType": "distro-only",
                    "active": True,
                    "forms": [151],
                }
            ],
        )
        self.assertEqual(
            [strip(s) for s in records["specimens"]],
            [
                {
                    "id": self.specimen.pk,
                    "form": 1,
                    "nickname": "Bulba",
                    "ability": None,
                    "language": "en",
                    "gender": "male",
                    "nature": "hardy",
                    "isAlpha": False,
                    "isShiny": True,
                    "isFromGo": False,
                    "capturedAt": "2024-09-23",
                    "pokeball": "poke-ball",
                    "observation": None,
                    "ot": self.ot.pk,
                    "location": self.save.pk,
                    "locationSince": "2026-03-12",
                }
            ],
        )
        self.assertEqual(
            [
                (s["row"], s["col"], s["dex"], s["form"], s["specimen"])
                for s in records["slots"][:3]
            ],
            [
                (0, 0, self.dex.pk, 1, self.specimen.pk),
                (0, 1, self.dex.pk, 151, None),
                (0, 2, None, None, None),
            ],
        )
        self.assertEqual(len(records["slots"]), self.slots)
        self.assertEqual({s["box"] for s in records["slots"]}, {self.box.pk})

    def test_command_writes_the_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        out = StringIO()
        file = tmp / "sub" / "dados.json"
        call_command(
            "exportuserdata",
            "--output",
            str(file),
            "--catalog-version",
            "catalog-x",
            stdout=out,
        )
        data = json.loads(file.read_text(encoding="utf-8"))
        self.assertEqual(data["catalog"], "catalog-x")
        self.assertIn("specimens=1", out.getvalue())
        self.assertIn(f"slots={self.slots}", out.getvalue())
        self.assertIn("deposited=1", out.getvalue())

        with override_settings(BACKUPS_DIR=tmp):
            call_command("exportuserdata", stdout=StringIO())
        default = tmp / f"ishinydex-{date.today()}.json"
        self.assertEqual(json.loads(default.read_text(encoding="utf-8"))["catalog"], "")
