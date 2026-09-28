from pathlib import Path

from django.test import TestCase

from core.tests import factories as f
from pokedex.resolvers import PokemonSpriteResolver, SingleSpriteResolver

BASE = Path("/media/sprites/pokemon")


class PokemonSpriteResolverTests(TestCase):
    def test_default_form(self):
        _, pokemon, form = f.make_full_pokemon("bulbasaur", 1)

        path = PokemonSpriteResolver(pokemon, form, shiny=False).resolve(BASE)

        self.assertEqual(path, BASE / "1.png")

    def test_default_form_shiny(self):
        _, pokemon, form = f.make_full_pokemon("bulbasaur", 1)

        path = PokemonSpriteResolver(pokemon, form, shiny=True).resolve(BASE)

        self.assertEqual(path, BASE / "shiny/1.png")

    def test_non_default_form_uses_name_suffix(self):
        _, pokemon, _ = f.make_full_pokemon("unown", 201)
        form = f.make_form(pokemon, name="unown-b", is_default=False)

        path = PokemonSpriteResolver(pokemon, form, shiny=False).resolve(BASE)

        self.assertEqual(path, BASE / "201-b.png")

    def test_non_default_form_with_same_name_as_pokemon(self):
        _, pokemon, _ = f.make_full_pokemon("vivillon", 666)
        form = f.make_form(pokemon, name="vivillon", is_default=False)

        path = PokemonSpriteResolver(pokemon, form, shiny=False).resolve(BASE)

        self.assertEqual(path, BASE / "666.png")

    def test_female_form_of_species_with_gender_differences(self):
        _, pokemon, _ = f.make_full_pokemon(
            "pyroar-male", 668, has_gender_differences=True
        )
        form = f.make_form(pokemon, name="pyroar-female", is_default=False)

        path = PokemonSpriteResolver(pokemon, form, shiny=False).resolve(BASE)
        shiny_path = PokemonSpriteResolver(pokemon, form, shiny=True).resolve(BASE)

        self.assertEqual(path, BASE / "female/668.png")
        self.assertEqual(shiny_path, BASE / "shiny/female/668.png")

    def test_default_form_of_species_with_gender_differences_is_not_female(self):
        _, pokemon, form = f.make_full_pokemon(
            "pyroar-male", 668, has_gender_differences=True
        )

        path = PokemonSpriteResolver(pokemon, form, shiny=False).resolve(BASE)

        self.assertEqual(path, BASE / "668.png")


class SingleSpriteResolverTests(TestCase):
    def test_ignores_form_suffix(self):
        _, pokemon, _ = f.make_full_pokemon("sinistea", 854)
        form = f.make_form(pokemon, name="sinistea-antique", is_default=False)

        path = SingleSpriteResolver(pokemon, form, shiny=False).resolve(BASE)
        shiny_path = SingleSpriteResolver(pokemon, form, shiny=True).resolve(BASE)

        self.assertEqual(path, BASE / "854.png")
        self.assertEqual(shiny_path, BASE / "shiny/854.png")
