from pathlib import Path

from django.test import TestCase

from core.tests import factories as f
from core.tests.mixins import TempSpritesMixin
from pokedex.renderers import HomeSpriteRenderer, PokemonSpriteRenderer
from pokedex.resolvers import SingleSpriteResolver


class PokemonSpriteRendererTests(TempSpritesMixin, TestCase):
    def setUp(self):
        super().setUp()
        _, self.pokemon, self.form = f.make_full_pokemon("bulbasaur", 1)

    def test_form_sprite_url(self):
        self.add_sprite("pokemon/1.png")

        url = PokemonSpriteRenderer(self.form).get_sprite_url()

        self.assertEqual(url, Path("/media/sprites/pokemon/1.png"))

    def test_shiny_option(self):
        self.add_sprite("pokemon/shiny/1.png")

        url = PokemonSpriteRenderer(self.form, "shiny").get_sprite_url()

        self.assertEqual(url, Path("/media/sprites/pokemon/shiny/1.png"))

    def test_pokemon_uses_its_default_form(self):
        self.add_sprite("pokemon/1.png")
        f.make_form(self.pokemon, name="bulbasaur-other", is_default=False)

        renderer = PokemonSpriteRenderer(self.pokemon)

        self.assertEqual(renderer.form, self.form)
        self.assertEqual(
            renderer.get_sprite_url(), Path("/media/sprites/pokemon/1.png")
        )

    def test_pokemon_without_default_form(self):
        pokemon = f.make_pokemon(name="missingno")

        renderer = PokemonSpriteRenderer(pokemon)

        self.assertIsNone(renderer.pokemon)
        self.assertIsNone(renderer.form)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            PokemonSpriteRenderer(self.form).get_sprite_url()

    def test_missing_file_uses_existing_default(self):
        self.add_sprite("pokemon/0.png")
        default = Path("/media/sprites/pokemon/0.png")

        url = PokemonSpriteRenderer(self.form).get_sprite_url(default=default)

        self.assertEqual(url, default)

    def test_missing_file_and_missing_default_raises(self):
        with self.assertRaises(FileNotFoundError):
            PokemonSpriteRenderer(self.form).get_sprite_url(
                default=Path("/media/sprites/pokemon/0.png")
            )

    def test_resolver_override_by_pokemon_name(self):
        _, pokemon, form = f.make_full_pokemon("sinistea", 854)

        resolver = PokemonSpriteRenderer(form)._get_sprite_resolver()

        self.assertIsInstance(resolver, SingleSpriteResolver)

    def test_sprites_url_setter(self):
        self.add_sprite("pokemon/other/home/1.png")
        renderer = PokemonSpriteRenderer(self.form)

        renderer.sprites_url = "/media/sprites/pokemon/other/home"

        self.assertEqual(
            renderer.get_sprite_url(),
            Path("/media/sprites/pokemon/other/home/1.png"),
        )

    def test_sprites_url_setter_rejects_invalid_values(self):
        renderer = PokemonSpriteRenderer(self.form)

        with self.assertRaises(AttributeError):
            renderer.sprites_url = 123  # type: ignore[assignment]

        with self.assertRaises(AttributeError):
            renderer.sprites_url = "/media/sprites/does-not-exist"


class SlotSpriteRendererTests(TempSpritesMixin, TestCase):
    def setUp(self):
        super().setUp()
        _, _, self.form = f.make_full_pokemon("bulbasaur", 1)
        self.slot = f.make_box().slots.earliest("position")
        self.slot.form = self.form

    def test_slot_uses_its_form(self):
        renderer = HomeSpriteRenderer(self.slot)

        self.assertEqual(renderer.form, self.form)
        self.assertFalse(renderer.is_shiny_sprite)

    def test_slot_in_shiny_dex_defaults_to_shiny(self):
        self.slot.personal_dex = f.make_personal_dex(is_shiny_dex=True)

        self.assertTrue(HomeSpriteRenderer(self.slot).is_shiny_sprite)
        self.assertFalse(HomeSpriteRenderer(self.slot, "default").is_shiny_sprite)

    def test_slot_without_form(self):
        self.slot.form = None

        renderer = HomeSpriteRenderer(self.slot)

        self.assertIsNone(renderer.pokemon)
        self.assertIsNone(renderer.form)

    def test_home_sprite_url(self):
        self.add_sprite("pokemon/other/home/shiny/1.png")

        url = HomeSpriteRenderer(self.slot, "shiny").get_sprite_url()

        self.assertEqual(url, Path("/media/sprites/pokemon/other/home/shiny/1.png"))

    def test_invalid_object_raises(self):
        with self.assertRaises(ValueError):
            PokemonSpriteRenderer(object())  # type: ignore[arg-type]
