from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from core.tests import factories as f
from pokedex.models import PokemonAbility


class PokemonViewSetTests(APITestCase):
    def setUp(self):
        _, self.bulbasaur, self.bulbasaur_form = f.make_full_pokemon(
            "bulbasaur", 1, types=("grass", "poison"), abilities=("overgrow",)
        )
        f.make_stat(self.bulbasaur, "speed", 45)
        _, self.charmander, _ = f.make_full_pokemon("charmander", 4, types=("fire",))

    def test_list_is_paginated(self):
        response = self.client.get(reverse("api:pokemon-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            [p["name"] for p in response.data["results"]], ["bulbasaur", "charmander"]
        )

    def test_retrieve_serializes_relations_as_objects(self):
        response = self.client.get(
            reverse("api:pokemon-detail", args=[self.bulbasaur.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["types"],
            [{"slot": 1, "type": "grass"}, {"slot": 2, "type": "poison"}],
        )
        self.assertEqual(
            response.data["abilities"],
            [{"slot": 1, "ability": "overgrow", "is_hidden": False}],
        )
        self.assertEqual(
            response.data["stats"], [{"stat": "speed", "base_stat": 45, "effort": 0}]
        )
        self.assertNotIn("moves", response.data)
        self.assertNotIn("game_indices", response.data)

    def test_stats_follow_canonical_order_for_the_chart(self):
        pokemon = f.make_full_pokemon("pikachu", 25)[1]
        for stat, value in (
            ("speed", 90),
            ("special-defense", 50),
            ("hp", 35),
            ("attack", 55),
            ("special-attack", 50),
            ("defense", 40),
        ):
            f.make_stat(pokemon, stat, value)

        response = self.client.get(reverse("api:pokemon-detail", args=[pokemon.pk]))

        self.assertEqual(
            [(s["stat"], s["base_stat"]) for s in response.data["stats"]],
            [
                ("hp", 35),
                ("attack", 55),
                ("defense", 40),
                ("special-attack", 50),
                ("special-defense", 50),
                ("speed", 90),
            ],
        )

    def test_abilities_and_types_ordered_by_slot(self):
        pokemon = f.make_full_pokemon(
            "venusaur", 3, types=("grass", "poison"), abilities=("overgrow",)
        )[1]
        hidden = PokemonAbility.objects.create(
            slot=3, ability="chlorophyll", is_hidden=True
        )
        pokemon.abilities.add(hidden)

        response = self.client.get(reverse("api:pokemon-detail", args=[pokemon.pk]))

        self.assertEqual([a["slot"] for a in response.data["abilities"]], [1, 3])
        self.assertEqual([t["slot"] for t in response.data["types"]], [1, 2])

    def test_list_query_count_does_not_grow_with_page_size(self):
        for i in range(8):
            _, pokemon, _ = f.make_full_pokemon(
                f"extra-{i}", 100 + i, types=("water", "ice"), abilities=("swim",)
            )
            f.make_stat(pokemon, "hp", 50)

        # count + página + 1 prefetch por relação (abilities, stats, types)
        with self.assertNumQueries(5):
            response = self.client.get(reverse("api:pokemon-list"))

        self.assertEqual(len(response.data["results"]), 10)

    def test_filter_by_form_id(self):
        response = self.client.get(
            reverse("api:pokemon-list"), {"form_id": self.bulbasaur_form.pk}
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "bulbasaur")

    def test_is_read_only(self):
        response = self.client.post(reverse("api:pokemon-list"), {"name": "x"})

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
