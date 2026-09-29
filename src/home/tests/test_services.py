from django.test import TestCase

from core.tests import factories as f
from home.models import PersonalDex, Slot
from home.services import (
    BOX_SIZE,
    NotEnoughBoxes,
    allowed_genders,
    boxes_needed,
    create_default_dex,
    free_box_runs,
    plan_default_dex,
)


class BoxesNeededTests(TestCase):
    def forms(self, *names):
        return [f.make_full_pokemon(name, i)[2] for i, name in enumerate(names, 1)]

    def test_counts_full_and_partial_boxes(self):
        self.assertEqual(boxes_needed([], force_new_box=False), 0)
        forms = self.forms(*(f"mon-{i}" for i in range(BOX_SIZE + 1)))
        self.assertEqual(boxes_needed(forms, force_new_box=False), 2)

    def test_force_new_box_starts_each_generation_in_a_new_box(self):
        forms = self.forms("bulbasaur", "ivysaur", "chikorita", "bayleef")

        self.assertEqual(boxes_needed(forms, force_new_box=False), 1)
        # chikorita (1ª da geração II) vai para o 1º slot da box seguinte.
        self.assertEqual(boxes_needed(forms, force_new_box=True), 2)

    def test_generation_starting_at_first_slot_does_not_skip(self):
        forms = self.forms("chikorita", "bayleef")

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

    def test_not_enough_boxes_creates_nothing(self):
        for box in (self.small, self.first, self.second):
            Slot.objects.filter(box=box, row=0, col=0).update(form=self.forms[1])

        with self.assertRaises(NotEnoughBoxes) as error:
            create_default_dex("Living")

        self.assertEqual(error.exception.plan.boxes_needed, 1)
        self.assertEqual(error.exception.plan.largest_free_run, 0)
        self.assertFalse(PersonalDex.objects.exists())


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
