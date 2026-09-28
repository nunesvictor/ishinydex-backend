from pathlib import Path
from unittest import mock

from django.contrib.admin.sites import site
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import translation

from core.admin import TimestampedAdmin
from core.admin_mixins import CustomFieldsRendererMixin
from core.forms import AdminModelForm
from core.tests import factories as f
from core.tests.mixins import TempSpritesMixin
from home.models import Box
from pokedex.models import PokemonSpecies


class CustomFieldsRendererMixinTests(TempSpritesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.mixin = CustomFieldsRendererMixin()
        _, self.pokemon, self.form = f.make_full_pokemon(
            "bulbasaur", 1, types=("grass", "poison")
        )
        self.add_sprite("pokemon/1.png")

    def test_get_type_sprite(self):
        self.assertEqual(
            self.mixin.get_type_sprite("fire"),
            Path("/media/sprites/types/generation-viii/sword-shield/10.png"),
        )
        self.assertEqual(
            self.mixin.get_type_sprite(
                "fire", generation="generation-iii", game_version="emerald"
            ),
            Path("/media/sprites/types/generation-iii/emerald/10.png"),
        )

    def test_render_types(self):
        html = self.mixin.render_types(self.form)

        self.assertIn("sword-shield/12.png", html)
        self.assertIn("sword-shield/4.png", html)
        self.assertLess(html.index("12.png"), html.index("4.png"))

    def test_render_types_without_types(self):
        self.assertEqual(self.mixin.render_types(f.make_form()), "-")

    def test_render_sprite_none(self):
        self.assertEqual(self.mixin.render_sprite(None), "-")

    def test_render_sprite_marks_unregistered(self):
        html = self.mixin.render_sprite(self.form)

        self.assertIn("pokemon-sprite status-unregistred", html)

    def test_render_sprite_registered(self):
        html = self.mixin.render_sprite(self.form, is_registered=True)

        self.assertNotIn("status-unregistred", html)

    def test_render_sprite_free_slot(self):
        slot = f.make_box().slots.first()

        with translation.override("en"):
            self.assertIn("free slot", self.mixin.render_sprite(slot))

    def test_render_sprite_slot_with_mismatched_specimen_blinks(self):
        _, _, other_form = f.make_full_pokemon("charmander", 4)
        self.add_sprite("pokemon/other/home/1.png")
        slot = f.make_box().slots.first()
        slot.form = self.form
        slot.specimen = f.make_specimen(other_form)

        html = self.mixin.render_sprite(slot, is_registered=True)

        self.assertIn("status-blinking", html)


class TimestampedAdminTests(SimpleTestCase):
    def test_timestamps_are_read_only(self):
        model_admin = site._registry[Box]

        self.assertIsInstance(model_admin, TimestampedAdmin)
        self.assertLessEqual(
            {"created_at", "updated_at"},
            set(model_admin.get_readonly_fields(RequestFactory().get("/"))),
        )


class SpeciesForm(AdminModelForm):
    class Meta:
        model = PokemonSpecies
        fields = ("name", "color", "growth_rate")


class AdminModelFormTests(TestCase):
    def setUp(self):
        f.make_species(color="green", growth_rate="medium-slow")
        f.make_species(color="red", growth_rate="medium-slow")
        f.make_species(color="green", growth_rate="slow")

    def _choices(self, form, field_name):
        return list(form.fields[field_name].widget.choices)

    def test_choices_come_from_existing_values(self):
        form = SpeciesForm()

        form._set_select_fields("color")
        form._set_select_fields("growth_rate")
        form._set_select_fields("not_a_field")

        self.assertEqual(
            self._choices(form, "color"),
            [("", "---------"), ("green", "green"), ("red", "red")],
        )
        self.assertEqual(
            self._choices(form, "growth_rate"),
            [("", "---------"), ("medium-slow", "medium-slow"), ("slow", "slow")],
        )

    def test_current_value_is_always_an_option(self):
        species = PokemonSpecies(color="purple")

        form = SpeciesForm(instance=species)
        form._set_select_fields("color")

        self.assertIn(("purple", "purple"), self._choices(form, "color"))

    @mock.patch("requests.get", side_effect=AssertionError("network access"))
    def test_species_admin_form_works_offline(self, _get):
        from pokedex.forms import PokemonSpeciesAdminForm

        form = PokemonSpeciesAdminForm()

        self.assertIn(("red", "red"), self._choices(form, "color"))


class SpriteTemplateTagTests(TempSpritesMixin, TestCase):
    template = Template("{% load sprites %}{% banner_sprite_img obj 64 64 %}")

    def setUp(self):
        super().setUp()
        _, _, self.form = f.make_full_pokemon("bulbasaur", 1)
        self.add_sprite("pokemon/other/home/1.png")
        self.add_sprite("pokemon/other/home/shiny/1.png")
        self.slot = f.make_box().slots.first()
        self.slot.form = self.form

    def render(self, obj):
        return self.template.render(Context({"obj": obj}))

    def test_unregistered_slot_blinks(self):
        html = self.render(self.slot)

        self.assertIn("/pokemon/other/home/1.png", html)
        self.assertIn("status-unregistred", html)
        self.assertIn("status-blinking", html)
        self.assertIn('width="64"', html)

    def test_slot_in_shiny_dex(self):
        self.slot.personal_dex = f.make_personal_dex(is_shiny_dex=True)

        self.assertIn("/pokemon/other/home/shiny/1.png", self.render(self.slot))

    def test_registered_slot(self):
        self.slot.specimen = f.make_specimen(self.form, is_shiny=True)

        html = self.render(self.slot)

        self.assertIn("/pokemon/other/home/shiny/1.png", html)
        self.assertNotIn("status-", html)


class PreserveGetParamsTagTests(SimpleTestCase):
    template = Template(
        "{% load admin_urls_extra %}{% preserve_get_params box__id__exact=box p=page %}"
    )

    def render(self, query, **ctx):
        request = RequestFactory().get("/", query)
        return self.template.render(Context({"request": request, **ctx}))

    def test_sets_and_removes_params(self):
        self.assertEqual(
            self.render({"q": "bulba", "p": "2"}, box=5, page=""),
            "q=bulba&amp;box__id__exact=5",
        )

    def test_without_request(self):
        self.assertEqual(self.template.render(Context({"box": 1})), "")
