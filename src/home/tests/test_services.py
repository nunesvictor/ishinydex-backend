from unittest import mock

from django.test import TestCase

from core.tests import factories as f
from home.models import Box, PersonalDex, Slot
from home.services import (
    BOX_SIZE,
    NotEnoughBoxes,
    allowed_genders,
    boxes_needed,
    create_boxes,
    create_default_dex,
    delete_dex,
    free_box_runs,
    plan_default_dex,
)


class BoxesNeededTests(TestCase):
    def forms(self, *entries):
        """``entries``: pares (nome, nº nacional)."""
        return [f.make_full_pokemon(name, number)[2] for name, number in entries]

    def test_counts_full_and_partial_boxes(self):
        self.assertEqual(boxes_needed([], force_new_box=False), 0)
        forms = self.forms(*((f"mon-{i}", i) for i in range(1, BOX_SIZE + 2)))
        self.assertEqual(boxes_needed(forms, force_new_box=False), 2)

    def test_force_new_box_starts_each_generation_in_a_new_box(self):
        forms = self.forms(
            ("bulbasaur", 1), ("ivysaur", 2), ("chikorita", 152), ("bayleef", 153)
        )

        self.assertEqual(boxes_needed(forms, force_new_box=False), 1)
        # chikorita (1ª da geração II) vai para o 1º slot da box seguinte.
        self.assertEqual(boxes_needed(forms, force_new_box=True), 2)

    def test_generation_break_does_not_depend_on_the_starter(self):
        # Sem o Chikorita: a geração II começa no Bayleef, pela espécie.
        forms = self.forms(("bulbasaur", 1), ("bayleef", 153), ("meganium", 154))

        self.assertEqual(boxes_needed(forms, force_new_box=True), 2)

    def test_generation_starting_at_first_slot_does_not_skip(self):
        forms = self.forms(("chikorita", 152), ("bayleef", 153))

        self.assertEqual(boxes_needed(forms, force_new_box=True), 1)


class FreeBoxRunsTests(TestCase):
    def test_splits_on_boxes_with_form_or_dex(self):
        a, b, c, d, e = (f.make_box(name=f"B{i}") for i in range(5))
        form = f.make_full_pokemon("bulbasaur", 1)[2]
        Slot.objects.filter(box=b, row=0, col=0).update(form=form)
        Slot.objects.filter(box=d, row=4, col=5).update(
            personal_dex=f.make_personal_dex(name="Outro")
        )

        self.assertEqual(free_box_runs(), [[a], [c], [e]])


class CreateDefaultDexTests(TestCase):
    def setUp(self):
        self.forms = [
            f.make_full_pokemon(name, i)[2]
            for i, name in enumerate(("bulbasaur", "ivysaur", "venusaur"), 1)
        ]
        # Forma só de batalha: fica fora do conjunto padrão.
        f.make_form(self.forms[0].pokemon, name="venusaur-mega", is_battle_only=True)
        self.small, self.used, self.first, self.second = (
            f.make_box(name=f"HOME {i}") for i in range(1, 5)
        )
        Slot.objects.filter(box=self.used, row=0, col=0).update(form=self.forms[0])

    def test_plan_without_creating(self):
        plan = plan_default_dex(force_new_box=False)

        self.assertEqual(plan.forms, self.forms)
        self.assertEqual(plan.boxes_needed, 1)
        self.assertEqual(plan.largest_free_run, 2)
        self.assertEqual(plan.boxes, [self.small])
        self.assertFalse(PersonalDex.objects.exists())

    def test_creates_dex_and_installs_scheme_in_first_free_run(self):
        dex = create_default_dex("Living", is_shiny_dex=True)

        self.assertTrue(dex.is_shiny_dex)
        self.assertEqual(list(dex.forms.all()), self.forms)
        installed = Slot.objects.filter(personal_dex=dex).order_by("position")
        self.assertEqual([s.form for s in installed], self.forms)
        self.assertEqual({s.box for s in installed}, {self.small})

    def test_skips_runs_that_are_too_short(self):
        # Ocupa a 1ª box livre: a próxima sequência livre (HOME 3–4) serve.
        Slot.objects.filter(box=self.small, row=0, col=0).update(form=self.forms[1])

        dex = create_default_dex("Living")

        boxes = {s.box for s in Slot.objects.filter(personal_dex=dex)}
        self.assertEqual(boxes, {self.first})

    @mock.patch("home.services.HOME_MAX_BOXES", 4)
    def test_not_enough_boxes_creates_nothing(self):
        for box in (self.small, self.first, self.second):
            Slot.objects.filter(box=box, row=0, col=0).update(form=self.forms[1])

        with self.assertRaises(NotEnoughBoxes) as error:
            create_default_dex("Living")

        self.assertEqual(error.exception.plan.boxes_needed, 1)
        self.assertEqual(error.exception.plan.largest_free_run, 0)
        self.assertFalse(PersonalDex.objects.exists())
        self.assertEqual(Box.objects.count(), 4)

    def occupy(self, *boxes):
        for box in boxes:
            Slot.objects.filter(box=box, row=0, col=0).update(form=self.forms[1])

    def test_creates_missing_box_at_the_end(self):
        self.occupy(self.small, self.first, self.second)

        plan = plan_default_dex(force_new_box=False)
        self.assertTrue(plan.enough_space)
        self.assertEqual((plan.boxes, plan.boxes_to_create), ([], 1))

        dex = create_default_dex("Living")

        new_box = Box.objects.get(name="HOME 5")
        self.assertEqual(new_box.position, 5)
        self.assertEqual(new_box.slots.count(), BOX_SIZE)
        installed = Slot.objects.filter(personal_dex=dex).order_by("position")
        self.assertEqual([s.form for s in installed], self.forms)
        self.assertEqual({s.box for s in installed}, {new_box})

    @mock.patch("home.services.boxes_needed", return_value=2)
    def test_completes_the_trailing_free_run(self, _):
        # Livre só HOME 4 (a última): falta 1 box, criada depois dela.
        self.occupy(self.small, self.first)

        plan = plan_default_dex(force_new_box=False)
        self.assertEqual((plan.boxes, plan.boxes_to_create), ([self.second], 1))

        dex = create_default_dex("Living")

        self.assertTrue(Box.objects.filter(name="HOME 5").exists())
        boxes = {s.box for s in Slot.objects.filter(personal_dex=dex)}
        self.assertEqual(boxes, {self.second})

    @mock.patch("home.services.boxes_needed", return_value=2)
    def test_free_run_in_the_middle_is_not_completed(self, _):
        # HOME 1 livre, mas a última box está em uso: as novas não a continuam.
        self.occupy(self.first, self.second)

        plan = plan_default_dex(force_new_box=False)

        self.assertEqual((plan.boxes, plan.boxes_to_create), ([], 2))

    @mock.patch("home.services.HOME_MAX_BOXES", 4)
    def test_never_goes_past_home_limit(self):
        self.occupy(self.small, self.first, self.second)

        self.assertFalse(plan_default_dex(force_new_box=False).enough_space)
        with self.assertRaises(NotEnoughBoxes):
            create_default_dex("Living")
        self.assertEqual(Box.objects.count(), 4)

    def test_without_boxes_creates_them(self):
        Box.objects.all().delete()

        dex = create_default_dex("Living")

        self.assertEqual(list(Box.objects.values_list("name", flat=True)), ["HOME 1"])
        self.assertEqual(Slot.objects.filter(personal_dex=dex).count(), 3)


class CreateBoxesTests(TestCase):
    def test_names_follow_position_skipping_used_names(self):
        f.make_box(name="HOME 1")
        f.make_box(name="HOME 3")

        boxes = create_boxes(2)

        self.assertEqual([b.name for b in boxes], ["HOME 4", "HOME 5"])
        self.assertEqual([b.position for b in boxes], [3, 4])
        self.assertEqual(create_boxes(0), [])


class AllowedGendersTests(TestCase):
    def form(self, name, gender_rate):
        species, _, form = f.make_full_pokemon(name, 1)
        species.gender_rate = gender_rate
        species.save()
        return form

    def test_by_species_gender_rate(self):
        self.assertEqual(allowed_genders(self.form("magnemite", -1)), {"genderless"})
        self.assertEqual(allowed_genders(self.form("tauros", 0)), {"male"})
        self.assertEqual(allowed_genders(self.form("chansey", 8)), {"female"})
        self.assertEqual(allowed_genders(self.form("pikachu", 4)), {"male", "female"})

    def test_gender_forms_win_over_species(self):
        # Na base importada, oinkologne tem gender_rate 0 ("só macho").
        self.assertEqual(allowed_genders(self.form("oinkologne-female", 0)), {"female"})
        self.assertEqual(allowed_genders(self.form("meowstic-male", 4)), {"male"})

    def test_form_without_pokemon_accepts_any(self):
        self.assertEqual(
            allowed_genders(f.make_form(pokemon=None, name="x")),
            {"male", "female", "genderless"},
        )


class DeleteDexTests(TestCase):
    def test_frees_slots_and_keeps_specimens(self):
        form = f.make_full_pokemon("bulbasaur", 1)[2]
        box = f.make_box(name="HOME 1")
        dex = f.make_personal_dex(form, name="Living")
        specimen = f.make_specimen(form)
        Slot.objects.filter(box=box, row=0, col=0).update(
            form=form, personal_dex=dex, specimen=specimen
        )

        delete_dex(dex)

        self.assertFalse(PersonalDex.objects.exists())
        self.assertEqual(free_box_runs(), [[box]])
        specimen.refresh_from_db()
        self.assertFalse(Slot.objects.filter(specimen=specimen).exists())
