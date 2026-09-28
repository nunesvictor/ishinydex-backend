from unittest import mock

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.tests import factories as f
from core.tests.mixins import TempSpritesMixin
from pokedex.admin_filters import EggGroupFilter
from pokedex.models import PokemonSpecies


class EggGroupFilterTests(TestCase):
    def setUp(self):
        self.model_admin = site._registry[PokemonSpecies]
        self.request = RequestFactory().get("/")
        f.make_species(name="bulbasaur", egg_groups=["monster", "plant"])
        f.make_species(name="charmander", egg_groups=["monster", "dragon"])
        f.make_species(name="ditto", egg_groups=["ditto"])
        f.make_species(name="unknown", egg_groups=[])

    def _filter(self, value=None):
        params = {"egg_group": [value]} if value else {}
        return EggGroupFilter(self.request, params, PokemonSpecies, self.model_admin)

    def test_lookups_are_unique_and_sorted(self):
        lookups = self._filter().lookups(self.request, self.model_admin)

        self.assertEqual(
            lookups,
            [
                ("ditto", "Ditto"),
                ("dragon", "Dragon"),
                ("monster", "Monster"),
                ("plant", "Plant"),
            ],
        )

    def test_queryset_filters_by_group(self):
        qs = self._filter("monster").queryset(self.request, PokemonSpecies.objects)

        self.assertQuerySetEqual(
            qs.order_by("name"), ["bulbasaur", "charmander"], transform=str
        )

    def test_queryset_without_value_is_untouched(self):
        qs = self._filter().queryset(self.request, PokemonSpecies.objects.all())

        self.assertEqual(qs.count(), 4)


class PokedexAdminViewsTests(TempSpritesMixin, TestCase):
    """Smoke tests: as telas do admin do pokedex renderizam sem erro."""

    def setUp(self):
        super().setUp()
        self.client.force_login(
            get_user_model().objects.create_superuser("admin", "a@a.com", "pw")
        )
        self.species, self.pokemon, self.form = f.make_full_pokemon(
            "bulbasaur", 1, types=("grass", "poison"), national_dex=1
        )
        self.add_sprite("pokemon/1.png")
        self.add_sprite("pokemon/other/home/1.png")
        self.add_sprite("types/generation-viii/sword-shield/12.png")
        self.add_sprite("types/generation-viii/sword-shield/4.png")

    def test_changelists(self):
        for model in ("pokemon", "pokemonform", "pokemonspecies", "shinylock"):
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:pokedex_{model}_changelist"))

                self.assertEqual(response.status_code, 200)

    def test_species_changelist_renders_national_dex_and_types(self):
        response = self.client.get(reverse("admin:pokedex_pokemonspecies_changelist"))

        self.assertContains(
            response, "/media/sprites/types/generation-viii/sword-shield/12.png"
        )
        self.assertContains(response, "/media/sprites/pokemon/other/home/1.png")

    def test_pokemon_change_view_with_forms_inline(self):
        """Regressão: a página quebrava com RecursionError (linha vazia do inline)."""
        f.make_form(self.pokemon, name="bulbasaur-other", is_default=False)
        self.add_sprite("pokemon/1-other.png")

        response = self.client.get(
            reverse("admin:pokedex_pokemon_change", args=[self.pokemon.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/media/sprites/pokemon/1.png")
        self.assertContains(response, "/media/sprites/pokemon/1-other.png")
        self.assertFalse(
            response.context["inline_admin_formsets"][0].has_add_permission
        )

    def test_species_changelist_tolerates_missing_data(self):
        f.make_species(name="incomplete")

        response = self.client.get(reverse("admin:pokedex_pokemonspecies_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "incomplete")

    @mock.patch("requests.get", side_effect=AssertionError("network access"))
    def test_species_change_view_works_offline(self, _get):
        response = self.client.get(
            reverse("admin:pokedex_pokemonspecies_change", args=[self.species.pk])
        )

        self.assertEqual(response.status_code, 200)

    def test_add_is_disabled_for_pokeapi_models(self):
        for model in ("pokemon", "pokemonform", "pokemonspecies", "move"):
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:pokedex_{model}_add"))

                self.assertEqual(response.status_code, 403)
