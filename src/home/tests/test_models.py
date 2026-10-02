from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import translation

from core.tests import factories as f
from home.models import DEFAULT_POKEMON_BOX_SIZE, Box, Slot, Specimen


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

    def test_default_ordering_is_position(self):
        # Box.Meta herda o ``ordering`` de OrderedModel.Meta.
        first, second = f.make_box(), f.make_box()
        Box.objects.filter(pk=first.pk).update(position=3)

        self.assertEqual(list(Box.objects.all()), [second, first])

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

        slot = box.slots.earliest("position")
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

    def test_str_is_translated(self):
        """Regressão: a tradução era aplicada depois do format() e nunca batia."""
        with translation.override("pt-br"):
            self.assertEqual(str(self.slot), "[HOME 1: 1,1] slot livre")

            self.slot.form = self.form
            self.assertEqual(
                str(self.slot),
                "[HOME 1: 1,1] (bulbasaur): nenhum espécime depositado",
            )


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


class OriginVersionTests(TestCase):
    """``Specimen.origin_version`` é derivado do OT (ver home.origin_marks)."""

    def setUp(self):
        _, _, self.form = f.make_full_pokemon("bulbasaur", 1)
        sv = f.make_version_group(name="scarlet-violet")
        self.scarlet = f.make_version(name="scarlet", version_group=sv)
        self.violet = f.make_version(name="violet", version_group=sv)
        self.sword = f.make_version(
            name="sword", version_group=f.make_version_group(name="sword-shield")
        )

    def reload(self, specimen) -> Specimen:
        return Specimen.objects.get(pk=specimen.pk)

    def test_new_specimen_gets_ot_version(self):
        specimen = f.make_specimen(self.form, ot=f.make_ot(version=self.scarlet))

        self.assertEqual(self.reload(specimen).origin_version, self.scarlet)

    def test_ot_without_version_or_no_ot_leaves_it_empty(self):
        without_version = f.make_specimen(self.form, ot=f.make_ot())
        without_ot = f.make_specimen(self.form)

        self.assertIsNone(self.reload(without_version).origin_version)
        self.assertIsNone(self.reload(without_ot).origin_version)

    def test_changing_ot_derives_again(self):
        specimen = f.make_specimen(self.form, ot=f.make_ot(version=self.scarlet))
        specimen = self.reload(specimen)

        specimen.ot = f.make_ot(version=self.sword)
        specimen.save()
        self.assertEqual(self.reload(specimen).origin_version, self.sword)

        specimen.ot = None
        specimen.save(update_fields=["ot"])
        self.assertIsNone(self.reload(specimen).origin_version)

    def test_saving_without_changing_ot_keeps_manual_correction(self):
        specimen = self.reload(
            f.make_specimen(self.form, ot=f.make_ot(version=self.scarlet))
        )
        specimen.origin_version = self.sword  # correção manual (admin)
        specimen.save()

        specimen = self.reload(specimen)
        specimen.nickname = "Bulba"
        specimen.save()

        self.assertEqual(self.reload(specimen).origin_version, self.sword)

    def test_ot_gaining_version_fills_its_specimens(self):
        ot = f.make_ot()
        specimens = [f.make_specimen(self.form, ot=ot) for _ in range(2)]
        other = f.make_specimen(self.form, ot=f.make_ot(trainer_id="999"))

        ot = type(ot).objects.get(pk=ot.pk)
        ot.version = self.scarlet
        ot.save()

        for specimen in specimens:
            self.assertEqual(self.reload(specimen).origin_version, self.scarlet)
        self.assertIsNone(self.reload(other).origin_version)

    def test_ot_changing_version_keeps_manual_corrections(self):
        ot = f.make_ot(version=self.scarlet)
        derived = f.make_specimen(self.form, ot=ot)
        corrected = self.reload(f.make_specimen(self.form, ot=ot))
        corrected.origin_version = self.sword
        corrected.save()

        ot = type(ot).objects.get(pk=ot.pk)
        ot.version = self.violet
        ot.save()
        self.assertEqual(self.reload(derived).origin_version, self.violet)
        self.assertEqual(self.reload(corrected).origin_version, self.sword)

        ot.version = None
        ot.save()
        self.assertIsNone(self.reload(derived).origin_version)
        self.assertEqual(self.reload(corrected).origin_version, self.sword)

    def test_saving_ot_without_changing_version_does_not_touch_specimens(self):
        ot = f.make_ot(version=self.scarlet)
        specimen = self.reload(f.make_specimen(self.form, ot=ot))
        specimen.origin_version = None
        specimen.save()

        ot = type(ot).objects.get(pk=ot.pk)
        ot.name = "Red"
        ot.save()

        self.assertIsNone(self.reload(specimen).origin_version)

    def test_origin_mark(self):
        specimen = f.make_specimen(self.form, ot=f.make_ot(version=self.scarlet))
        self.assertEqual(self.reload(specimen).origin_mark, "paldea")

        specimen.is_from_go = True
        self.assertEqual(specimen.origin_mark, "go")

        self.assertIsNone(f.make_specimen(self.form).origin_mark)
