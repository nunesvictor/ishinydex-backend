from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import translation

from core.tests import factories as f
from home.models import DEFAULT_POKEMON_BOX_SIZE, Box, Slot


class BoxTests(TestCase):
    def test_creating_a_box_creates_its_30_slots(self):
        box = f.make_box()

        self.assertEqual(box.slots.count(), DEFAULT_POKEMON_BOX_SIZE)
        self.assertEqual(
            list(box.slots.values_list("row", "col"))[:7],
            [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (1, 0)],
        )
        self.assertEqual(list(box.slots.values_list("row", "col"))[-1], (4, 5))

    def test_saving_again_does_not_duplicate_slots(self):
        box = f.make_box()

        box.name = "renamed"
        box.save()

        self.assertEqual(box.slots.count(), DEFAULT_POKEMON_BOX_SIZE)

    def test_positions_are_sequential(self):
        first, second = f.make_box(), f.make_box()

        self.assertEqual((first.position, second.position), (1, 2))
        self.assertEqual(
            list(Slot.objects.values_list("position", flat=True)), list(range(1, 61))
        )

    def test_position_is_kept_on_update(self):
        box = f.make_box()
        f.make_box()

        box.save()

        box.refresh_from_db()
        self.assertEqual(box.position, 1)

    def test_page(self):
        boxes = [Box(name=str(i), position=i) for i in (1, 30, 31, 60, 61)]

        self.assertEqual([b.page for b in boxes], [1, 1, 2, 2, 3])

    def test_is_empty_considers_forms(self):
        box = f.make_box()
        self.assertTrue(box.is_empty)

        slot = box.slots.first()
        slot.form = f.make_full_pokemon("bulbasaur", 1)[2]
        slot.save()

        self.assertFalse(box.is_empty)

    def test_timestamp_and_position_fields_are_last(self):
        names = [field.name for field in Box._meta.local_fields]

        self.assertEqual(names[-3:], ["position", "created_at", "updated_at"])


class SlotTests(TestCase):
    def setUp(self):
        self.box = f.make_box(name="HOME 1")
        self.slot = self.box.slots.get(row=0, col=0)
        _, _, self.form = f.make_full_pokemon("bulbasaur", 1)

    def test_flags(self):
        last = self.box.slots.get(row=4, col=5)

        self.assertTrue(self.slot.is_first)
        self.assertFalse(last.is_first)
        self.assertTrue(self.slot.is_free)
        self.assertTrue(self.slot.is_empty)

        self.slot.form = self.form
        self.slot.specimen = f.make_specimen(self.form)

        self.assertFalse(self.slot.is_free)
        self.assertFalse(self.slot.is_empty)

    def test_clean_rejects_specimen_of_other_form(self):
        _, _, other_form = f.make_full_pokemon("charmander", 4)
        self.slot.form = self.form
        self.slot.specimen = f.make_specimen(other_form)

        with self.assertRaises(ValidationError) as ctx:
            self.slot.clean()

        self.assertIn("specimen", ctx.exception.message_dict)

    def test_clean_accepts_matching_specimen(self):
        self.slot.form = self.form
        self.slot.specimen = f.make_specimen(self.form)

        self.slot.clean()

    def test_str(self):
        with translation.override("en"):
            self.assertEqual(str(self.slot), "[HOME 1: 1,1] free slot")

            self.slot.form = self.form
            self.assertEqual(
                str(self.slot), "[HOME 1: 1,1] (bulbasaur): no specimen deposited"
            )

            self.slot.specimen = f.make_specimen(
                self.form, nickname="Bulba", is_shiny=True
            )
            self.assertEqual(str(self.slot), "[HOME 1: 1,1] (bulbasaur): Bulba ✨")


class SpecimenTests(TestCase):
    def setUp(self):
        _, _, self.form = f.make_full_pokemon("bulbasaur", 1)

    def test_form_name_is_filled_from_form(self):
        specimen = f.make_specimen(self.form)

        self.assertEqual(specimen.form_name, "bulbasaur")

    def test_explicit_form_name_is_kept(self):
        specimen = f.make_specimen(self.form, form_name="custom")

        self.assertEqual(specimen.form_name, "custom")

    def test_defaults(self):
        specimen = f.make_specimen(self.form)

        self.assertEqual(
            (specimen.language, specimen.gender, specimen.nature),
            ("en", "male", "hardy"),
        )
        self.assertFalse(specimen.is_shiny)

    def test_str_with_badges(self):
        specimen = f.make_specimen(
            self.form,
            nickname="Bulba",
            is_shiny=True,
            is_alpha=True,
            is_from_go=True,
            observation="note",
        )

        self.assertEqual(str(specimen), "Bulba ✨💢📱❗")

    def test_str_falls_back_to_form_name(self):
        specimen = f.make_specimen(self.form, is_shiny=True)

        self.assertEqual(str(specimen), "bulbasaur ✨")


class OriginalTrainerTests(TestCase):
    def test_str(self):
        ot = f.make_ot(name="Ash", trainer_id="123456")
        self.assertEqual(str(ot), "123456:Ash")

        ot.version = f.make_version(name="red")
        self.assertEqual(str(ot), "123456:Ash (red)")
