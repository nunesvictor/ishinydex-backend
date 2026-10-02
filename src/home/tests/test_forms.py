from typing import cast

from django import forms
from django.test import TestCase

from core.tests import factories as f
from core.tests.mixins import TempSpritesMixin
from home.choices import Pokeball
from home.forms import ImageSelectWidget, SpecimenAdminForm, SpecimenBulkUpdateForm


class ImageSelectWidgetTests(TestCase):
    def test_options_get_class_and_image(self):
        widget = ImageSelectWidget(
            choices=[("", "---"), ("a", "A"), ("b", "B")],
            image_map={"a": "/img/a.png"},
            attrs={"class": "select2-image-select"},
        )

        options = {
            opt["value"]: opt
            for group in widget.optgroups("field", [])
            for opt in group[1]
        }

        self.assertEqual(options["a"]["attrs"]["data-image"], "/img/a.png")
        self.assertNotIn("data-image", options["b"]["attrs"])
        self.assertEqual(options["b"]["attrs"]["class"], "select2-image-select")


class SpecimenAdminFormTests(TempSpritesMixin, TestCase):
    def setUp(self):
        super().setUp()
        _, _, self.form = f.make_full_pokemon(
            "bulbasaur", 1, abilities=("overgrow", "chlorophyll")
        )

    def _ability_choices(self, form):
        return list(form.fields["ability"].choices)

    def test_without_form_only_blank_ability(self):
        form = SpecimenAdminForm()

        self.assertEqual(self._ability_choices(form), [("", "---------")])

    def test_abilities_from_instance_form(self):
        specimen = f.make_specimen(self.form)

        form = SpecimenAdminForm(instance=specimen)

        self.assertEqual(
            self._ability_choices(form),
            [
                ("", "---------"),
                ("chlorophyll", "chlorophyll"),
                ("overgrow", "overgrow"),
            ],
        )

    def test_abilities_from_initial_form_id(self):
        form = SpecimenAdminForm(initial={"form_id": self.form.pk})

        self.assertIn(("overgrow", "overgrow"), self._ability_choices(form))

    def test_abilities_from_posted_form(self):
        form = SpecimenAdminForm(data={"form": self.form.pk})

        self.assertIn(("overgrow", "overgrow"), self._ability_choices(form))

    def test_valid_submission(self):
        form = SpecimenAdminForm(
            data={
                "form": self.form.pk,
                "ability": "overgrow",
                "language": "en",
                "gender": "female",
                "nature": "bold",
                "pokeball": Pokeball.DREAM_BALL,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        specimen = form.save()
        self.assertEqual(specimen.ability, "overgrow")
        self.assertEqual(specimen.form_name, "bulbasaur")

    def test_rejects_ability_of_other_pokemon(self):
        form = SpecimenAdminForm(
            data={
                "form": self.form.pk,
                "ability": "blaze",
                "language": "en",
                "gender": "male",
                "nature": "hardy",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("ability", form.errors)

    def test_pokeball_widget_has_sprites(self):
        form = SpecimenAdminForm()
        widget = form.fields["pokeball"].widget

        self.assertIsInstance(widget, ImageSelectWidget)
        self.assertEqual(
            widget.image_map[Pokeball.POKE_BALL.value],
            "/media/sprites/items/poke-ball.png",
        )
        self.assertEqual(len(widget.image_map), len(Pokeball))


class SpecimenBulkUpdateFormTests(TempSpritesMixin, TestCase):
    def setUp(self):
        super().setUp()
        _, _, form = f.make_full_pokemon("bulbasaur", 1)
        self.specimen = f.make_specimen(form)

    def _form(self, **data):
        return SpecimenBulkUpdateForm(data={"specimens": [self.specimen.pk], **data})

    def test_every_updatable_field_starts_as_keep_current(self):
        form = SpecimenBulkUpdateForm()

        self.assertEqual(
            [name for name in form.fields if name != "specimens"],
            list(SpecimenBulkUpdateForm.UPDATABLE_FIELDS),
        )
        for name in SpecimenBulkUpdateForm.UPDATABLE_FIELDS:
            with self.subTest(field=name):
                self.assertFalse(form.fields[name].required)
                self.assertIsNone(form[name].initial)

    def test_select_fields_offer_keep_current_first(self):
        form = SpecimenBulkUpdateForm()

        for name in ("language", "gender", "nature", "is_shiny", "pokeball"):
            with self.subTest(field=name):
                # Em runtime, ``choices`` de um ChoiceField é sempre uma lista.
                choices = cast(list, cast(forms.ChoiceField, form.fields[name]).choices)
                self.assertEqual(choices[0], SpecimenBulkUpdateForm.KEEP_CURRENT)

        self.assertEqual(
            cast(forms.ModelChoiceField, form.fields["ot"]).empty_label,
            SpecimenBulkUpdateForm.KEEP_CURRENT[1],
        )

    def test_nothing_filled_means_no_updates(self):
        form = self._form()

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_updates(), {})

    def test_default_values_can_be_applied(self):
        """Regressão: valores iguais ao default do model eram descartados."""
        form = self._form(
            nature="hardy", gender="male", language="en", is_shiny="false"
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.get_updates(),
            {"nature": "hardy", "gender": "male", "language": "en", "is_shiny": False},
        )

    def test_boolean_values(self):
        form = self._form(is_alpha="true", is_from_go="false", is_shiny="")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_updates(), {"is_alpha": True, "is_from_go": False})

    def test_foreign_key_text_and_pokeball(self):
        ot = f.make_ot()

        form = self._form(ot=ot.pk, pokeball=Pokeball.BEAST_BALL, observation="event")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.get_updates(),
            {"ot": ot, "pokeball": Pokeball.BEAST_BALL, "observation": "event"},
        )

    def test_invalid_choice(self):
        form = self._form(nature="not-a-nature")

        self.assertFalse(form.is_valid())
        self.assertIn("nature", form.errors)

    def test_pokeball_widget_has_sprites(self):
        widget = SpecimenBulkUpdateForm().fields["pokeball"].widget

        self.assertIsInstance(widget, ImageSelectWidget)
        self.assertEqual(len(widget.image_map), len(Pokeball))

    def test_requires_specimens(self):
        form = SpecimenBulkUpdateForm(data={})

        self.assertFalse(form.is_valid())
        self.assertIn("specimens", form.errors)
