import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.db.models import Q
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from api.serializers.home import type_sprite_url
from core.tests import factories as f
from home.models import Box, PersonalDex, Slot, Specimen
from pokedex.models import PokemonForm, PokemonSpeciesDexEntry


class HomeAPITestCase(APITestCase):
    """Um dex shiny com duas boxes: a 1ª com bulbasaur (depositado) e
    charmander (vazio); a 2ª com squirtle (vazio). Uma 3ª box não pertence ao
    dex."""

    def setUp(self):
        self.client.force_authenticate(User.objects.create_user("ash"))

        _, _, self.bulbasaur = f.make_full_pokemon(
            "bulbasaur", 1, abilities=("overgrow", "chlorophyll")
        )
        _, _, self.charmander = f.make_full_pokemon("charmander", 4)
        _, _, self.squirtle = f.make_full_pokemon("squirtle", 7)

        self.dex = f.make_personal_dex(
            self.bulbasaur,
            self.charmander,
            self.squirtle,
            name="Shiny Dex",
            is_shiny_dex=True,
        )
        self.box1 = f.make_box(name="HOME 1")
        self.box2 = f.make_box(name="HOME 2")
        self.other_box = f.make_box(name="HOME 3")

        self.bulbasaur_specimen = f.make_specimen(self.bulbasaur, is_shiny=True)
        self.bulbasaur_slot = self.set_slot(
            self.box1, 0, 0, self.bulbasaur, self.bulbasaur_specimen
        )
        self.charmander_slot = self.set_slot(self.box1, 0, 1, self.charmander)
        # slot do dex, mas sem forma (espaço livre)
        self.free_slot = self.set_slot(self.box1, 0, 2, None)
        self.squirtle_slot = self.set_slot(self.box2, 0, 0, self.squirtle)

    def set_slot(self, box, row, col, form, specimen=None, dex=None) -> Slot:
        slot = box.slots.get(row=row, col=col)
        slot.personal_dex = dex or self.dex
        slot.form = form
        slot.specimen = specimen
        slot.save()
        return slot


class PersonalDexViewSetTests(HomeAPITestCase):
    def test_list_counts_total_and_registered(self):
        other_dex = f.make_personal_dex(name="Living Dex")
        self.set_slot(self.other_box, 0, 0, self.charmander, dex=other_dex)

        response = self.client.get(reverse("api:personal-dex-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"],
            [
                {
                    "id": other_dex.pk,
                    "name": "Living Dex",
                    "is_shiny_dex": False,
                    "force_new_box": False,
                    "total": 1,
                    "registered": 0,
                },
                {
                    "id": self.dex.pk,
                    "name": "Shiny Dex",
                    "is_shiny_dex": True,
                    "force_new_box": False,
                    "total": 3,
                    "registered": 1,
                },
            ],
        )

    def test_retrieve(self):
        response = self.client.get(
            reverse("api:personal-dex-detail", args=[self.dex.pk])
        )

        self.assertEqual(response.data["total"], 3)
        self.assertEqual(response.data["registered"], 1)

    def test_generations_in_box_order_with_counts(self):
        species, _, chikorita = f.make_full_pokemon("chikorita", 152)
        species.generation = "generation-ii"
        species.save()
        # Geração II começa na HOME 2, depois da I (HOME 1 e 2).
        self.set_slot(self.box2, 0, 1, chikorita)
        # Slot de outro dex não conta.
        self.set_slot(
            self.other_box, 0, 0, chikorita, dex=f.make_personal_dex(name="Outro")
        )

        with self.assertNumQueries(3):  # dex, agregação, boxes
            response = self.client.get(
                reverse("api:personal-dex-generations", args=[self.dex.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        box1 = {"id": self.box1.pk, "name": "HOME 1", "position": self.box1.position}
        box2 = {"id": self.box2.pk, "name": "HOME 2", "position": self.box2.position}
        self.assertEqual(
            response.data,
            [
                {
                    "generation": "generation-i",
                    "total": 3,
                    "registered": 1,
                    "first_box": box1,
                },
                {
                    "generation": "generation-ii",
                    "total": 1,
                    "registered": 0,
                    "first_box": box2,
                },
            ],
        )

    def test_preview_does_not_create(self):
        # HOME 1 e 2 são do dex; HOME 3 está livre. Formas: as 3 do setUp.
        response = self.client.get(
            reverse("api:personal-dex-preview"), {"force_new_box": "true"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "forms": 3,
                "boxes_needed": 1,
                "largest_free_run": 1,
                "enough_space": True,
                "boxes_to_create": 0,
                "first_box": {
                    "id": self.other_box.pk,
                    "name": "HOME 3",
                    "position": self.other_box.position,
                },
            },
        )
        self.assertEqual(PersonalDex.objects.count(), 1)

    def test_preview_creating_boxes(self):
        # Todas as boxes em uso: o dex iria para uma box nova, no fim.
        self.set_slot(self.other_box, 0, 0, self.charmander, dex=self.dex)

        response = self.client.get(reverse("api:personal-dex-preview"))

        self.assertTrue(response.data["enough_space"])
        self.assertEqual(response.data["boxes_to_create"], 1)
        self.assertIsNone(response.data["first_box"])
        self.assertEqual(response.data["largest_free_run"], 0)
        self.assertEqual(Box.objects.count(), 3)

    @mock.patch("home.services.HOME_MAX_BOXES", 3)
    def test_preview_without_space(self):
        self.set_slot(self.other_box, 0, 0, self.charmander, dex=self.dex)

        response = self.client.get(reverse("api:personal-dex-preview"))

        self.assertFalse(response.data["enough_space"])
        self.assertEqual(response.data["boxes_to_create"], 0)
        self.assertIsNone(response.data["first_box"])

    def test_create_default_dex(self):
        response = self.client.post(
            reverse("api:personal-dex-list"),
            {"name": "Living Dex", "is_shiny_dex": False, "force_new_box": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        dex = PersonalDex.objects.get(name="Living Dex")
        self.assertEqual(
            response.data,
            {
                "id": dex.pk,
                "name": "Living Dex",
                "is_shiny_dex": False,
                "force_new_box": True,
                "total": 3,
                "registered": 0,
            },
        )
        self.assertEqual(
            set(Slot.objects.filter(personal_dex=dex).values_list("box", flat=True)),
            {self.other_box.pk},
        )

    def test_create_validation_errors(self):
        duplicate = self.client.post(
            reverse("api:personal-dex-list"), {"name": "Shiny Dex"}, format="json"
        )
        missing = self.client.post(reverse("api:personal-dex-list"), {}, format="json")

        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", duplicate.data)
        self.assertIn("name", missing.data)

    def test_create_creating_boxes(self):
        self.set_slot(self.other_box, 0, 0, self.charmander, dex=self.dex)

        response = self.client.post(
            reverse("api:personal-dex-list"), {"name": "Living Dex"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total"], 3)
        dex = PersonalDex.objects.get(name="Living Dex")
        self.assertEqual(
            set(
                Slot.objects.filter(personal_dex=dex).values_list(
                    "box__name", flat=True
                )
            ),
            {"HOME 4"},
        )

    @mock.patch("home.services.HOME_MAX_BOXES", 3)
    @mock.patch("api.views.home.HOME_MAX_BOXES", 3)
    def test_create_without_space(self):
        self.set_slot(self.other_box, 0, 0, self.charmander, dex=self.dex)

        response = self.client.post(
            reverse("api:personal-dex-list"), {"name": "Living Dex"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                "non_field_errors": [
                    "Não há boxes livres seguidas suficientes para este "
                    "PersonalDex: ele precisa de 1, a maior sequência livre "
                    "tem 0, e criar as boxes que faltam passaria das 3 boxes "
                    "do Pokémon HOME."
                ]
            },
        )
        self.assertFalse(PersonalDex.objects.filter(name="Living Dex").exists())

    def test_partial_update_renames_and_toggles_shiny(self):
        response = self.client.patch(
            reverse("api:personal-dex-detail", args=[self.dex.pk]),
            {"name": "Living Dex", "is_shiny_dex": False, "force_new_box": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "id": self.dex.pk,
                "name": "Living Dex",
                "is_shiny_dex": False,
                # Não muda: o esquema já está nas boxes.
                "force_new_box": False,
                "total": 3,
                "registered": 1,
            },
        )

    def test_partial_update_duplicate_name_is_400(self):
        f.make_personal_dex(name="Living Dex")

        response = self.client.patch(
            reverse("api:personal-dex-detail", args=[self.dex.pk]),
            {"name": "Living Dex"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_put_is_not_allowed(self):
        response = self.client.put(
            reverse("api:personal-dex-detail", args=[self.dex.pk]),
            {"name": "Living Dex"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_destroy_frees_slots_and_keeps_specimens(self):
        other_dex = f.make_personal_dex(name="Living Dex")
        other_slot = self.set_slot(self.other_box, 0, 0, self.charmander, dex=other_dex)

        response = self.client.delete(
            reverse("api:personal-dex-detail", args=[self.dex.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PersonalDex.objects.filter(pk=self.dex.pk).exists())
        # Os slots do dex ficam livres (sem forma, dex nem espécime)...
        self.assertFalse(
            Slot.objects.filter(
                Q(form__isnull=False)
                | Q(personal_dex__isnull=False)
                | Q(specimen__isnull=False),
                box__in=[self.box1, self.box2],
            ).exists()
        )
        # ...o espécime continua, agora disponível...
        specimen = self.client.get(
            reverse("api:specimen-detail", args=[self.bulbasaur_specimen.pk])
        )
        self.assertEqual(specimen.status_code, status.HTTP_200_OK)
        self.assertIsNone(specimen.data["slot"])
        # ...e o outro dex não muda.
        other_slot.refresh_from_db()
        self.assertEqual(other_slot.personal_dex, other_dex)
        self.assertEqual(other_slot.form, self.charmander)

    def test_destroy_unknown_dex_is_404(self):
        response = self.client.delete(reverse("api:personal-dex-detail", args=[9999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_generations_of_unknown_dex_is_404(self):
        response = self.client.get(reverse("api:personal-dex-generations", args=[9999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_boxes_only_with_dex_slots_ordered_by_position(self):
        response = self.client.get(
            reverse("api:personal-dex-boxes", args=[self.dex.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "id": self.box1.pk,
                    "name": "HOME 1",
                    "position": self.box1.position,
                    "total": 2,
                    "registered": 1,
                },
                {
                    "id": self.box2.pk,
                    "name": "HOME 2",
                    "position": self.box2.position,
                    "total": 1,
                    "registered": 0,
                },
            ],
        )

    def test_progress_of_shiny_dex_counts_only_shiny(self):
        # Não shiny pode ficar no slot de um shiny dex, mas não conta.
        self.charmander_slot.specimen = f.make_specimen(self.charmander)
        self.charmander_slot.save()
        url = reverse("api:personal-dex-detail", args=[self.dex.pk])

        dex = self.client.get(url).data
        boxes = self.client.get(reverse("api:personal-dex-boxes", args=[self.dex.pk]))
        generations = self.client.get(
            reverse("api:personal-dex-generations", args=[self.dex.pk])
        )

        self.assertEqual((dex["total"], dex["registered"]), (3, 1))
        self.assertEqual(
            [(b["total"], b["registered"]) for b in boxes.data], [(2, 1), (1, 0)]
        )
        self.assertEqual(
            [(g["total"], g["registered"]) for g in generations.data], [(3, 1)]
        )

    def test_progress_of_regular_dex_counts_shiny_and_not_shiny(self):
        living = f.make_personal_dex(name="Living Dex")
        self.set_slot(
            self.other_box,
            0,
            0,
            self.charmander,
            f.make_specimen(self.charmander),
            living,
        )
        self.set_slot(
            self.other_box,
            0,
            1,
            self.squirtle,
            f.make_specimen(self.squirtle, is_shiny=True),
            living,
        )
        url = reverse("api:personal-dex-detail", args=[living.pk])

        dex = self.client.get(url).data
        boxes = self.client.get(reverse("api:personal-dex-boxes", args=[living.pk]))
        generations = self.client.get(
            reverse("api:personal-dex-generations", args=[living.pk])
        )

        self.assertEqual((dex["total"], dex["registered"]), (2, 2))
        self.assertEqual([(b["total"], b["registered"]) for b in boxes.data], [(2, 2)])
        self.assertEqual(
            [(g["total"], g["registered"]) for g in generations.data], [(2, 2)]
        )

    def test_boxes_count_only_slots_of_the_dex(self):
        other_dex = f.make_personal_dex()
        self.set_slot(self.box1, 4, 5, self.squirtle, dex=other_dex)

        response = self.client.get(
            reverse("api:personal-dex-boxes", args=[self.dex.pk])
        )

        self.assertEqual(response.data[0]["total"], 2)

    def test_boxes_of_unknown_dex_is_404(self):
        response = self.client.get(reverse("api:personal-dex-boxes", args=[999999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class HuntTests(HomeAPITestCase):
    """Lista de caçadas. No setUp: bulbasaur shiny depositado (HOME 1),
    charmander vazio (HOME 1), squirtle vazio (HOME 2)."""

    def hunts(self, dex=None, **params):
        return self.client.get(
            reverse("api:personal-dex-hunts", args=[(dex or self.dex).pk]), params
        )

    def names(self, response) -> list[str]:
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [item["form"]["name"] for item in response.data["results"]]

    def reasons(self, response) -> dict[str, list[str]]:
        return {
            item["form"]["name"]: item["reasons"] for item in response.data["results"]
        }

    def test_default_lists_slots_without_shiny_in_box_order(self):
        # Espécime não shiny também precisa ser caçado.
        _, _, oddish = f.make_full_pokemon("oddish", 43)
        self.set_slot(self.box2, 0, 1, oddish, f.make_specimen(oddish))

        response = self.hunts()

        self.assertEqual(self.names(response), ["charmander", "squirtle", "oddish"])
        self.assertEqual(response.data["count"], 3)
        item = response.data["results"][0]
        self.assertEqual(item["id"], self.charmander_slot.pk)
        self.assertEqual(item["box"]["name"], "HOME 1")
        self.assertEqual((item["row"], item["col"]), (0, 1))
        self.assertIsNone(item["specimen"])
        self.assertEqual(item["reasons"], ["no_shiny"])
        self.assertIsNone(item["shiny_lock"])
        self.assertEqual(self.reasons(response)["oddish"], ["no_shiny"])  # não shiny

    def test_ignores_slots_of_other_dexes_and_free_slots(self):
        other = f.make_personal_dex(name="Outro", is_shiny_dex=True)
        self.set_slot(self.other_box, 0, 0, self.charmander, dex=other)

        self.assertEqual(self.names(self.hunts()), ["charmander", "squirtle"])
        self.assertEqual(self.names(self.hunts(other)), ["charmander"])

    def test_from_go(self):
        self.bulbasaur_specimen.is_from_go = True
        self.bulbasaur_specimen.save()

        self.assertNotIn("bulbasaur", self.names(self.hunts()))
        response = self.hunts(reasons="no_shiny,from_go")
        self.assertEqual(self.names(response), ["bulbasaur", "charmander", "squirtle"])
        self.assertEqual(self.reasons(response)["bulbasaur"], ["from_go"])
        self.assertEqual(self.names(self.hunts(reasons="from_go")), ["bulbasaur"])

    def test_pokeball_outside_accepted_balls(self):
        params = {"reasons": "pokeball", "accepted_balls": "poke-ball,premier-ball"}
        cases = {"great-ball": ["bulbasaur"], "premier-ball": [], None: []}
        for ball, expected in cases.items():
            with self.subTest(ball=ball):
                self.bulbasaur_specimen.pokeball = ball
                self.bulbasaur_specimen.save()
                self.assertEqual(self.names(self.hunts(**params)), expected)

    def test_pokeball_without_accepted_balls_is_ignored(self):
        self.bulbasaur_specimen.pokeball = "great-ball"
        self.bulbasaur_specimen.save()

        self.assertEqual(self.names(self.hunts(reasons="pokeball")), [])
        self.assertEqual(
            self.names(self.hunts(reasons="pokeball,no_shiny")),
            ["charmander", "squirtle"],
        )

    def test_reports_every_matching_reason(self):
        self.bulbasaur_specimen.is_from_go = True
        self.bulbasaur_specimen.pokeball = "great-ball"
        self.bulbasaur_specimen.save()

        response = self.hunts(reasons="from_go", accepted_balls="poke-ball")

        self.assertEqual(self.reasons(response), {"bulbasaur": ["from_go", "pokeball"]})

    def test_unknown_or_empty_reasons_list_nothing(self):
        self.assertEqual(self.names(self.hunts(reasons="")), [])
        self.assertEqual(self.names(self.hunts(reasons="foo")), [])
        self.assertEqual(
            self.names(self.hunts(reasons="foo,no_shiny")), ["charmander", "squirtle"]
        )

    def test_generation_and_type_any_of(self):
        species, _, pikipek = f.make_full_pokemon(
            "pikipek", 731, types=("normal", "flying")
        )
        species.generation = "generation-vii"
        species.save()
        self.set_slot(self.box2, 0, 1, pikipek)

        self.assertEqual(
            self.names(self.hunts(generation="generation-vii")), ["pikipek"]
        )
        # Qualquer um dos tipos: charmander e squirtle são "grass" na fábrica.
        self.assertEqual(self.names(self.hunts(type="flying,water")), ["pikipek"])
        self.assertEqual(
            self.names(self.hunts(type="grass,flying")),
            ["charmander", "squirtle", "pikipek"],
        )

    def test_categories(self):
        def add(name, number, col, *, abilities=(), **species_fields):
            species, _, form = f.make_full_pokemon(name, number, abilities=abilities)
            for field, value in species_fields.items():
                setattr(species, field, value)
            species.save()
            self.set_slot(self.box2, 1, col, form)

        add("mewtwo", 150, 0, is_legendary=True)
        add("mew", 151, 1, is_mythical=True)
        add("nihilego", 793, 2, abilities=("beast-boost",))
        add("pichu", 172, 3, is_baby=True)

        cases = {
            "legendary": ["mewtwo"],
            "mythical": ["mew"],
            "ultra-beast": ["nihilego"],
            "baby": ["pichu"],
            "regular": ["charmander", "squirtle"],
            "legendary,mythical,ultra-beast": ["mewtwo", "mew", "nihilego"],
            "foo": ["charmander", "squirtle", "mewtwo", "mew", "nihilego", "pichu"],
        }
        for category, expected in cases.items():
            with self.subTest(category=category):
                self.assertEqual(self.names(self.hunts(category=category)), expected)

    def test_example_gen7_legends_without_shiny_or_from_go(self):
        # Ex. 1 da issue: gen VII, lendário/mítico/UB, sem shiny ou shiny do GO.
        def add(name, number, col, specimen_fields=None, **species_fields):
            species, _, form = f.make_full_pokemon(name, number)
            species.generation = "generation-vii"
            for field, value in species_fields.items():
                setattr(species, field, value)
            species.save()
            specimen = specimen_fields and f.make_specimen(form, **specimen_fields)
            self.set_slot(self.box2, 2, col, form, specimen or None)

        add("tapu-koko", 785, 0, is_legendary=True)  # vazio
        add("solgaleo", 791, 1, {"is_shiny": True}, is_legendary=True)  # ok
        add(
            "magearna", 801, 2, {"is_shiny": True, "is_from_go": True}, is_mythical=True
        )
        add("rowlet", 722, 3)  # comum

        response = self.hunts(
            generation="generation-vii",
            category="legendary,mythical,ultra-beast",
            reasons="no_shiny,from_go",
        )

        self.assertEqual(
            self.reasons(response),
            {"tapu-koko": ["no_shiny"], "magearna": ["from_go"]},
        )

    def test_search(self):
        self.assertEqual(self.names(self.hunts(search="squir")), ["squirtle"])

    def test_search_humanized_name(self):
        _, _, iron_hands = f.make_full_pokemon("iron-hands", 992)
        self.set_slot(self.box2, 0, 1, iron_hands)

        for text in ("iron hands", "Iron  Hands", "iron-hands"):
            with self.subTest(text=text):
                self.assertEqual(self.names(self.hunts(search=text)), ["iron-hands"])

    def test_shiny_locks(self):
        f.make_shinylock(self.charmander, lock_type="unobtainable")
        f.make_shinylock(self.squirtle, lock_type="distro-only")
        # Lock inativo não conta.
        _, _, oddish = f.make_full_pokemon("oddish", 43)
        f.make_shinylock(oddish, lock_type="unobtainable", active=False)
        self.set_slot(self.box2, 0, 1, oddish)

        response = self.hunts()
        self.assertEqual(self.names(response), ["squirtle", "oddish"])
        locks = {i["form"]["name"]: i["shiny_lock"] for i in response.data["results"]}
        self.assertEqual(locks, {"squirtle": "distro-only", "oddish": None})

        response = self.hunts(include_locked="true")
        self.assertEqual(self.names(response), ["charmander", "squirtle", "oddish"])
        self.assertEqual(response.data["results"][0]["shiny_lock"], "unobtainable")

    def test_query_count_does_not_grow_with_results(self):
        for col in range(1, 6):
            _, _, form = f.make_full_pokemon(f"extra-{col}", 900 + col)
            self.set_slot(self.box2, 0, col, form)

        with self.assertNumQueries(4):  # dex, count, página, nº nacional
            response = self.hunts()

        self.assertEqual(response.data["count"], 7)

    def test_not_shiny_dex_is_400(self):
        dex = f.make_personal_dex(name="Living Dex")

        response = self.hunts(dex)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_unknown_dex_is_404(self):
        response = self.client.get(reverse("api:personal-dex-hunts", args=[9999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SlotSearchTests(HomeAPITestCase):
    def setUp(self):
        super().setUp()
        _, venusaur, self.venusaur = f.make_full_pokemon("venusaur", 3, national_dex=3)
        self.venusaur_alt = f.make_form(
            venusaur, name="venusaur-alt", pokeapi_id=10033, form_order=2
        )
        self.venusaur_slot = self.set_slot(self.box2, 0, 1, self.venusaur)
        self.alt_slot = self.set_slot(self.box2, 0, 2, self.venusaur_alt)
        # Mesma forma em outro dex: não entra na busca deste.
        other_dex = f.make_personal_dex(name="Outro")
        self.set_slot(self.other_box, 0, 0, self.venusaur, dex=other_dex)

    def search(self, text):
        response = self.client.get(
            reverse("api:slot-list"),
            {"personal_dex": self.dex.pk, "search": text},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [slot["id"] for slot in response.data["results"]]

    def test_by_name_is_case_insensitive_and_paginated(self):
        self.assertEqual(self.search("VENU"), [self.venusaur_slot.pk, self.alt_slot.pk])
        self.assertEqual(self.search("char"), [self.charmander_slot.pk])

    def test_by_national_dex_number_includes_alternate_forms(self):
        self.assertEqual(self.search("3"), [self.venusaur_slot.pk, self.alt_slot.pk])

    def test_by_form_pokeapi_id(self):
        self.assertEqual(self.search("10033"), [self.alt_slot.pk])
        self.assertEqual(self.search(" 1 "), [self.bulbasaur_slot.pk])

    def test_no_match(self):
        self.assertEqual(self.search("mewtwo"), [])
        self.assertEqual(self.search("999"), [])

    def test_by_humanized_name(self):
        # Os nomes são slugs da PokéAPI; a busca aceita o nome como se escreve.
        _, _, mr_mime = f.make_full_pokemon("mr-mime", 122)
        _, _, flabebe = f.make_full_pokemon("flabebe", 669)
        mr_mime_slot = self.set_slot(self.box2, 1, 0, mr_mime)
        flabebe_slot = self.set_slot(self.box2, 1, 1, flabebe)

        for text in ("mr mime", "Mr. Mime", "MR  MIME", "mr-mime"):
            with self.subTest(text=text):
                self.assertEqual(self.search(text), [mr_mime_slot.pk])
        self.assertEqual(self.search("Flabébé"), [flabebe_slot.pk])
        # Só pontuação: busca o texto cru (e não tudo).
        self.assertEqual(self.search("."), [])


class NationalNumberTests(HomeAPITestCase):
    def setUp(self):
        super().setUp()
        _, venusaur, self.venusaur = f.make_full_pokemon("venusaur", 3, national_dex=3)
        self.venusaur_alt = f.make_form(
            venusaur, name="venusaur-alt", pokeapi_id=10033, form_order=2
        )
        self.specimen = f.make_specimen(self.venusaur, nickname="Vovó")
        self.alt_specimen = f.make_specimen(self.venusaur_alt)

    def search_specimens(self, text):
        response = self.client.get(reverse("api:specimen-list"), {"search": text})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [s["id"] for s in response.data["results"]]

    def test_specimen_search_by_national_dex_includes_alternate_forms(self):
        self.assertEqual(
            self.search_specimens("3"), [self.specimen.pk, self.alt_specimen.pk]
        )

    def test_specimen_search_by_form_pokeapi_id(self):
        self.assertEqual(self.search_specimens("10033"), [self.alt_specimen.pk])
        self.assertEqual(self.search_specimens("999"), [])

    def test_specimen_search_by_text_is_unchanged(self):
        self.assertEqual(self.search_specimens("vov"), [self.specimen.pk])

    def test_specimen_search_humanized_form_name_and_raw_nickname(self):
        self.assertEqual(self.search_specimens("venusaur alt"), [self.alt_specimen.pk])
        # O apelido é texto livre: comparado sem virar slug.
        nicknamed = f.make_specimen(self.charmander, nickname="Big Boss")
        self.assertEqual(self.search_specimens("big boss"), [nicknamed.pk])

    def test_form_ref_has_species_national_number(self):
        response = self.client.get(reverse("api:specimen-list"), {"search": "venu"})

        numbers = {
            s["form_ref"]["name"]: s["form_ref"]["national_number"]
            for s in response.data["results"]
        }
        self.assertEqual(numbers, {"venusaur": 3, "venusaur-alt": 3})

    def test_national_number_is_null_without_entry(self):
        response = self.client.get(
            reverse("api:form-detail", args=[self.charmander.pk])
        )

        self.assertIsNone(response.data["national_number"])

    def test_national_number_without_prefetch(self):
        response = self.client.post(
            reverse("api:specimen-list"),
            {"form": self.venusaur_alt.pk, "is_shiny": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["form_ref"]["national_number"], 3)


class SlotViewSetTests(HomeAPITestCase):
    def test_list_by_box_returns_all_slots_without_pagination(self):
        with self.assertNumQueries(2):  # slots, nº nacional
            response = self.client.get(reverse("api:slot-list"), {"box": self.box1.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 30)
        self.assertEqual(
            [(s["row"], s["col"]) for s in response.data[:3]],
            [(0, 0), (0, 1), (0, 2)],
        )

    def test_slot_representation(self):
        Specimen.objects.filter(pk=self.bulbasaur_specimen.pk).update(
            gender="female", is_from_go=True
        )
        response = self.client.get(
            reverse("api:slot-list"), {"box": self.box1.pk, "personal_dex": self.dex.pk}
        )

        registered, empty, free = response.data
        self.assertEqual(
            registered["box"],
            {"id": self.box1.pk, "name": "HOME 1", "position": self.box1.position},
        )
        self.assertEqual(registered["form"]["name"], "bulbasaur")
        self.assertEqual(
            registered["form"]["sprite_url"],
            "http://testserver/media/sprites/pokemon/other/home/1.png",
        )
        self.assertEqual(
            registered["form"]["shiny_sprite_url"],
            "http://testserver/media/sprites/pokemon/other/home/shiny/1.png",
        )
        self.assertEqual(registered["specimen"]["id"], self.bulbasaur_specimen.pk)
        self.assertEqual(registered["specimen"]["gender"], "female")
        self.assertIs(registered["specimen"]["is_from_go"], True)
        self.assertTrue(registered["is_shiny_display"])

        # slot vazio num dex shiny também é exibido como shiny
        self.assertIsNone(empty["specimen"])
        self.assertTrue(empty["is_shiny_display"])

        self.assertIsNone(free["form"])
        self.assertFalse(free["is_shiny_display"])

    def test_non_shiny_specimen_is_not_shiny_display(self):
        self.bulbasaur_specimen.is_shiny = False
        self.bulbasaur_specimen.save()

        response = self.client.get(
            reverse("api:slot-detail", args=[self.bulbasaur_slot.pk])
        )

        self.assertFalse(response.data["is_shiny_display"])

    def test_specimen_summary_has_ability(self):
        self.bulbasaur_specimen.ability = "chlorophyll"
        self.bulbasaur_specimen.save()

        response = self.client.get(
            reverse("api:slot-detail", args=[self.bulbasaur_slot.pk])
        )

        self.assertEqual(response.data["specimen"]["ability"], "chlorophyll")

    def test_list_filter_registered(self):
        url = reverse("api:slot-list")

        registered = self.client.get(
            url, {"personal_dex": self.dex.pk, "registered": "true"}
        )
        missing = self.client.get(
            url, {"personal_dex": self.dex.pk, "registered": "false"}
        )

        self.assertEqual(
            [s["id"] for s in registered.data["results"]], [self.bulbasaur_slot.pk]
        )
        self.assertEqual(
            [s["id"] for s in missing.data["results"]],
            [self.charmander_slot.pk, self.squirtle_slot.pk],
        )

    def test_list_without_box_is_paginated(self):
        response = self.client.get(reverse("api:slot-list"), {"page_size": 5})

        self.assertEqual(response.data["count"], 90)
        self.assertEqual(len(response.data["results"]), 5)

    def test_page_size_is_capped(self):
        f.make_box()  # 120 slots no total

        response = self.client.get(reverse("api:slot-list"), {"page_size": 1000})

        self.assertEqual(len(response.data["results"]), 100)


class DepositTests(HomeAPITestCase):
    def deposit(self, slot, specimen_id):
        return self.client.post(
            reverse("api:slot-deposit", args=[slot.pk]),
            {"specimen_id": specimen_id},
            format="json",
        )

    def test_valid_deposit(self):
        specimen = f.make_specimen(self.charmander, is_shiny=True)

        response = self.deposit(self.charmander_slot, specimen.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.charmander_slot.pk)
        self.assertEqual(response.data["specimen"]["id"], specimen.pk)
        self.charmander_slot.refresh_from_db()
        self.assertEqual(self.charmander_slot.specimen, specimen)

    def test_different_form_is_400(self):
        specimen = f.make_specimen(self.squirtle)

        response = self.deposit(self.charmander_slot, specimen.pk)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {"specimen_id": ["a forma do espécime não corresponde à forma do slot."]},
        )
        self.charmander_slot.refresh_from_db()
        self.assertIsNone(self.charmander_slot.specimen)

    def test_specimen_deposited_elsewhere_is_400(self):
        other_slot = self.set_slot(self.other_box, 0, 0, self.bulbasaur)

        response = self.deposit(other_slot, self.bulbasaur_specimen.pk)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {"specimen_id": ["este espécime já está depositado em outro slot."]},
        )

    def test_redeposit_in_same_slot_is_ok(self):
        response = self.deposit(self.bulbasaur_slot, self.bulbasaur_specimen.pk)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_slot_without_form_is_400(self):
        specimen = f.make_specimen(self.charmander)

        response = self.deposit(self.free_slot, specimen.pk)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                "non_field_errors": [
                    "este slot não tem forma; não é possível depositar espécimes nele."
                ]
            },
        )

    def test_unknown_specimen_is_400(self):
        response = self.deposit(self.charmander_slot, 999999)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("specimen_id", response.data)

    def test_unknown_slot_is_404(self):
        response = self.client.post(
            reverse("api:slot-deposit", args=[999999]), {"specimen_id": 1}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_withdraw(self):
        response = self.client.post(
            reverse("api:slot-withdraw", args=[self.bulbasaur_slot.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["specimen"])
        self.bulbasaur_slot.refresh_from_db()
        self.assertIsNone(self.bulbasaur_slot.specimen)
        self.assertTrue(Specimen.objects.filter(pk=self.bulbasaur_specimen.pk).exists())


class SpecimenViewSetTests(HomeAPITestCase):
    def test_filter_alpha_and_from_go(self):
        alpha = f.make_specimen(self.bulbasaur, is_alpha=True)
        go = f.make_specimen(self.bulbasaur, is_from_go=True)
        both = f.make_specimen(self.bulbasaur, is_alpha=True, is_from_go=True)

        def ids(**params):
            response = self.client.get(reverse("api:specimen-list"), params)
            return {s["id"] for s in response.data["results"]}

        self.assertEqual(ids(is_alpha="true"), {alpha.pk, both.pk})
        self.assertEqual(ids(is_from_go="true"), {go.pk, both.pk})
        self.assertEqual(ids(is_alpha="true", is_from_go="true"), {both.pk})
        self.assertNotIn(alpha.pk, ids(is_alpha="false"))

    def test_filter_ids(self):
        a = f.make_specimen(self.charmander)
        b = f.make_specimen(self.charmander, is_shiny=True)
        f.make_specimen(self.charmander)

        def ids(**params):
            response = self.client.get(reverse("api:specimen-list"), params)
            return {s["id"] for s in response.data["results"]}

        self.assertEqual(ids(id=f"{a.pk},{b.pk}"), {a.pk, b.pk})
        # Combina com os outros filtros (E); valores inválidos são ignorados.
        self.assertEqual(ids(id=f"{a.pk},{b.pk}", is_shiny="true"), {b.pk})
        self.assertEqual(ids(id=f"x,{a.pk}"), {a.pk})
        self.assertEqual(ids(id="x"), set())
        self.assertEqual(
            self.client.get(reverse("api:specimen-ids"), {"id": f"{b.pk},{a.pk}"}).data,
            [a.pk, b.pk],
        )

    def test_filter_available(self):
        free = f.make_specimen(self.bulbasaur)

        available = self.client.get(reverse("api:specimen-list"), {"available": "true"})
        deposited = self.client.get(
            reverse("api:specimen-list"), {"available": "false"}
        )

        self.assertEqual([s["id"] for s in available.data["results"]], [free.pk])
        self.assertIsNone(available.data["results"][0]["slot"])
        self.assertEqual(
            [s["id"] for s in deposited.data["results"]], [self.bulbasaur_specimen.pk]
        )
        self.assertEqual(deposited.data["results"][0]["slot"], self.bulbasaur_slot.pk)

    def test_filters_form_shiny_and_search(self):
        charmander = f.make_specimen(self.charmander, nickname="Charizard Jr")
        f.make_specimen(self.squirtle, is_shiny=True)
        url = reverse("api:specimen-list")

        by_form = self.client.get(url, {"form_id": self.charmander.pk})
        not_shiny = self.client.get(url, {"is_shiny": "false"})
        by_nickname = self.client.get(url, {"search": "jr"})
        by_form_name = self.client.get(url, {"search": "SQUIRT"})

        self.assertEqual([s["id"] for s in by_form.data["results"]], [charmander.pk])
        self.assertEqual([s["id"] for s in not_shiny.data["results"]], [charmander.pk])
        self.assertEqual(
            [s["id"] for s in by_nickname.data["results"]], [charmander.pk]
        )
        self.assertEqual(by_form_name.data["count"], 1)

    def test_create(self):
        ot = f.make_ot()

        response = self.client.post(
            reverse("api:specimen-list"),
            {
                "form": self.bulbasaur.pk,
                "ability": "chlorophyll",
                "nature": "modest",
                "is_shiny": True,
                "ot": ot.pk,
                "pokeball": "dream-ball",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["form_name"], "bulbasaur")
        self.assertEqual(response.data["form_ref"]["id"], self.bulbasaur.pk)
        self.assertIsNone(response.data["slot"])
        self.assertEqual(
            response.data["pokeball_sprite_url"],
            "http://testserver/media/sprites/items/dream-ball.png",
        )

    def test_ability_must_belong_to_form(self):
        response = self.client.post(
            reverse("api:specimen-list"),
            {"form": self.bulbasaur.pk, "ability": "blaze"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {"ability": ["“blaze” não é uma habilidade válida para bulbasaur."]},
        )

    def test_partial_update_validates_ability_against_current_form(self):
        response = self.client.patch(
            reverse("api:specimen-detail", args=[self.bulbasaur_specimen.pk]),
            {"ability": "torrent"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ability", response.data)

    def test_partial_update_deposited_specimen(self):
        response = self.client.patch(
            reverse("api:specimen-detail", args=[self.bulbasaur_specimen.pk]),
            {"nickname": "Bulba", "is_alpha": True, "form": self.bulbasaur.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nickname"], "Bulba")
        self.assertTrue(response.data["is_alpha"])
        self.assertEqual(response.data["slot"], self.bulbasaur_slot.pk)

    def test_partial_update_cannot_change_form(self):
        response = self.client.patch(
            reverse("api:specimen-detail", args=[self.bulbasaur_specimen.pk]),
            {"form": self.charmander.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data, {"form": ["a forma de um espécime não pode ser alterada."]}
        )
        self.bulbasaur_specimen.refresh_from_db()
        self.assertEqual(self.bulbasaur_specimen.form, self.bulbasaur)

    def test_delete_deposited_specimen_releases_the_slot(self):
        response = self.client.delete(
            reverse("api:specimen-detail", args=[self.bulbasaur_specimen.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Specimen.objects.filter(pk=self.bulbasaur_specimen.pk).exists()
        )
        # O slot continua com a forma e fica faltante.
        self.bulbasaur_slot.refresh_from_db()
        self.assertIsNone(self.bulbasaur_slot.specimen)
        self.assertEqual(self.bulbasaur_slot.form, self.bulbasaur)

    def test_delete_available_specimen(self):
        specimen = f.make_specimen(self.bulbasaur)

        response = self.client.delete(
            reverse("api:specimen-detail", args=[specimen.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Specimen.objects.filter(pk=specimen.pk).exists())

    def ids(self, **params) -> list[int]:
        response = self.client.get(reverse("api:specimen-list"), params)
        return [s["id"] for s in response.data["results"]]

    def test_filter_pokeball(self):
        dive = f.make_specimen(self.charmander, pokeball="dive-ball")
        dusk = f.make_specimen(self.charmander, pokeball="dusk-ball")
        without = self.bulbasaur_specimen

        self.assertEqual(self.ids(pokeball="dive-ball"), [dive.pk])
        self.assertEqual(self.ids(pokeball="dive-ball, dusk-ball"), [dive.pk, dusk.pk])
        self.assertEqual(self.ids(pokeball="none"), [without.pk])
        self.assertEqual(
            set(self.ids(pokeball="none,dusk-ball")), {without.pk, dusk.pk}
        )
        self.assertEqual(self.ids(pokeball=",,"), [without.pk, dive.pk, dusk.pk])

    def test_filter_ot(self):
        ash, misty = f.make_ot(), f.make_ot()
        by_ash = f.make_specimen(self.charmander, ot=ash)
        by_misty = f.make_specimen(self.charmander, ot=misty)

        self.assertEqual(self.ids(ot=str(ash.pk)), [by_ash.pk])
        self.assertEqual(self.ids(ot=f"{ash.pk},{misty.pk}"), [by_ash.pk, by_misty.pk])
        self.assertEqual(self.ids(ot="none"), [self.bulbasaur_specimen.pk])
        self.assertEqual(self.ids(ot="abc"), [])

    def test_filter_type_requires_all_types(self):
        _, _, pidgey = f.make_full_pokemon("pidgey", 16, types=("normal", "flying"))
        _, _, wingull = f.make_full_pokemon("wingull", 278, types=("water", "flying"))
        pidgey_specimen = f.make_specimen(pidgey)
        wingull_specimen = f.make_specimen(wingull)

        self.assertEqual(
            self.ids(type="flying"), [pidgey_specimen.pk, wingull_specimen.pk]
        )
        self.assertEqual(self.ids(type="water,flying"), [wingull_specimen.pk])
        self.assertEqual(self.ids(type="grass"), [self.bulbasaur_specimen.pk])
        self.assertEqual(self.ids(type="fire,flying"), [])

    def test_filter_generation(self):
        species, _, turtwig = f.make_full_pokemon("turtwig", 387)
        species.generation = "generation-iv"
        species.save()
        specimen = f.make_specimen(turtwig)

        self.assertEqual(self.ids(generation="generation-iv"), [specimen.pk])
        self.assertEqual(
            self.ids(generation="generation-i,generation-iv"),
            [self.bulbasaur_specimen.pk, specimen.pk],
        )

    def test_filter_gender_nature_language_and_ability(self):
        female = f.make_specimen(
            self.charmander, gender="female", nature="jolly", language="ja"
        )
        genderless = f.make_specimen(self.charmander, gender="genderless")
        blaze = f.make_specimen(self.charmander, ability="blaze")

        self.assertEqual(
            self.ids(gender="female,genderless"), [female.pk, genderless.pk]
        )
        self.assertEqual(self.ids(nature="jolly"), [female.pk])
        self.assertEqual(self.ids(language="ja"), [female.pk])
        self.assertEqual(self.ids(ability="BLA"), [blaze.pk])
        solar = f.make_specimen(self.charmander, ability="solar-power")
        self.assertEqual(self.ids(ability="Solar Power"), [solar.pk])
        self.assertEqual(self.ids(gender="female", language="en"), [])

    def test_filter_captured_range(self):
        january = f.make_specimen(self.charmander, captured_at=date(2026, 1, 10))
        march = f.make_specimen(self.charmander, captured_at=date(2026, 3, 5))

        self.assertEqual(self.ids(captured_after="2026-03-05"), [march.pk])
        self.assertEqual(self.ids(captured_before="2026-01-10"), [january.pk])
        self.assertEqual(
            self.ids(captured_after="2026-01-01", captured_before="2026-12-31"),
            [january.pk, march.pk],
        )
        # data inválida: filtro ignorado
        self.assertEqual(len(self.ids(captured_after="ontem")), 3)

    def test_ordering(self):
        self.bulbasaur_specimen.captured_at = date(2026, 2, 1)
        self.bulbasaur_specimen.save()
        old = f.make_specimen(self.charmander, captured_at=date(2025, 1, 1))
        undated = f.make_specimen(self.squirtle)
        box_order = [self.bulbasaur_specimen.pk, old.pk, undated.pk]

        self.assertEqual(self.ids(), box_order)
        self.assertEqual(self.ids(ordering="box"), box_order)
        # O antigo "dex" não existe mais: cai no padrão.
        self.assertEqual(self.ids(ordering="dex"), box_order)
        self.assertEqual(
            self.ids(ordering="captured_at"),
            [old.pk, self.bulbasaur_specimen.pk, undated.pk],
        )
        self.assertEqual(
            self.ids(ordering="-captured_at"),
            [self.bulbasaur_specimen.pk, old.pk, undated.pk],
        )
        self.assertEqual(
            self.ids(ordering="-created_at"),
            [undated.pk, old.pk, self.bulbasaur_specimen.pk],
        )
        self.assertEqual(self.ids(ordering="nope"), box_order)

    def test_box_and_national_orderings(self):
        def national(form, number):
            form.pokemon.species.pokedex_numbers.add(
                PokemonSpeciesDexEntry.objects.create(
                    entry_number=number, pokedex="national"
                )
            )

        for form, number in (
            (self.bulbasaur, 1),
            (self.charmander, 4),
            (self.squirtle, 7),
        ):
            national(form, number)
        eevee = f.make_full_pokemon("eevee", 133, national_dex=133)[2]
        glaceon = f.make_full_pokemon("glaceon", 471, national_dex=471)[2]
        mew = f.make_full_pokemon("mew", 151, national_dex=151)[2]
        # Como na PokéAPI, o `order` agrupa a família: Glaceon vem primeiro.
        PokemonForm.objects.filter(pk=glaceon.pk).update(order=0)
        self.set_slot(self.box2, 0, 1, eevee)
        self.set_slot(self.box2, 0, 2, glaceon)
        # Squirtle também num 2º dex, na HOME 3, com um espécime depositado.
        other_dex = f.make_personal_dex(name="Outro")
        deposited = f.make_specimen(self.squirtle)
        self.set_slot(self.other_box, 0, 0, self.squirtle, deposited, dex=other_dex)

        c = f.make_specimen(self.charmander)
        s = f.make_specimen(self.squirtle)
        e = f.make_specimen(eevee)
        g = f.make_specimen(glaceon)
        m = f.make_specimen(mew)  # fora das boxes
        b = self.bulbasaur_specimen

        # Boxes: o próprio slot se depositado (HOME 3); senão o 1º slot da
        # forma (squirtle na HOME 2); fora das boxes por último.
        self.assertEqual(
            self.ids(ordering="box"),
            [b.pk, c.pk, s.pk, e.pk, g.pk, deposited.pk, m.pk],
        )
        # Nacional: 1, 4, 7, 7, 133, 151, 471.
        self.assertEqual(
            self.ids(ordering="national"),
            [b.pk, c.pk, deposited.pk, s.pk, e.pk, m.pk, g.pk],
        )

    def test_forms_of_same_species_follow_form_order(self):
        national = PokemonSpeciesDexEntry.objects.create(
            entry_number=1, pokedex="national"
        )
        self.bulbasaur.pokemon.species.pokedex_numbers.add(national)
        # O `order` da PokéAPI ao contrário do `form_order`: vale o form_order.
        other = f.make_form(
            self.bulbasaur.pokemon, name="bulbasaur-other", form_order=2, order=0
        )
        PokemonForm.objects.filter(pk=self.bulbasaur.pk).update(order=99)
        Specimen.objects.all().delete()
        later = f.make_specimen(other)
        first = f.make_specimen(self.bulbasaur)

        self.assertEqual(self.ids(ordering="national"), [first.pk, later.pk])
        self.assertEqual(self.ids(ordering="box"), [first.pk, later.pk])

    def test_ids_follow_filters_and_ordering(self):
        dive = f.make_specimen(self.charmander, pokeball="dive-ball")
        undated = f.make_specimen(self.squirtle)
        url = reverse("api:specimen-ids")

        everything = self.client.get(url)
        by_ball = self.client.get(url, {"pokeball": "dive-ball"})
        recent_first = self.client.get(url, {"ordering": "-created_at"})

        self.assertEqual(
            everything.data, [self.bulbasaur_specimen.pk, dive.pk, undated.pk]
        )
        self.assertEqual(by_ball.data, [dive.pk])
        self.assertEqual(
            recent_first.data, [undated.pk, dive.pk, self.bulbasaur_specimen.pk]
        )

    def bulk_release(self, data):
        return self.client.post(
            reverse("api:specimen-bulk-release"), data, format="json"
        )

    def test_bulk_release_deletes_and_frees_slots(self):
        loose = f.make_specimen(self.charmander)
        kept = f.make_specimen(self.squirtle)

        response = self.bulk_release(
            {"ids": [self.bulbasaur_specimen.pk, loose.pk, loose.pk]}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"released": 2})
        self.assertEqual(list(Specimen.objects.values_list("pk", flat=True)), [kept.pk])
        # Depositado: o slot continua com a forma, mas volta a faltar.
        self.bulbasaur_slot.refresh_from_db()
        self.assertIsNone(self.bulbasaur_slot.specimen)
        self.assertEqual(self.bulbasaur_slot.form, self.bulbasaur)

    def test_bulk_release_is_all_or_nothing(self):
        missing = self.bulk_release({"ids": [self.bulbasaur_specimen.pk, 999999]})
        empty = self.bulk_release({"ids": []})
        no_ids = self.bulk_release({})

        for response in (missing, empty, no_ids):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("ids", response.data)
        self.assertIn("999999", str(missing.data["ids"]))
        self.assertTrue(Specimen.objects.filter(pk=self.bulbasaur_specimen.pk).exists())

    def bulk(self, ids, changes):
        return self.client.patch(
            reverse("api:specimen-bulk"),
            {"ids": ids, "changes": changes},
            format="json",
        )

    def test_origin_version_and_mark(self):
        sv = f.make_version_group(name="scarlet-violet")
        ot = f.make_ot(version=f.make_version(name="violet", version_group=sv))
        specimen = f.make_specimen(self.charmander, ot=ot)
        go = f.make_specimen(self.charmander, ot=ot, is_from_go=True)
        unmarked = f.make_specimen(self.charmander)

        def detail(obj):
            url = reverse("api:specimen-detail", args=[obj.pk])
            data = self.client.get(url).data
            return data["origin_version"], data["origin_mark"]

        self.assertEqual(detail(specimen), ("violet", "paldea"))
        self.assertEqual(detail(go), ("violet", "go"))
        self.assertEqual(detail(unmarked), (None, None))

    def test_origin_version_is_read_only(self):
        red = f.make_version(name="red")
        specimen = f.make_specimen(self.charmander)

        response = self.client.patch(
            reverse("api:specimen-detail", args=[specimen.pk]),
            {"origin_version": red.name, "origin_mark": "go"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        specimen.refresh_from_db()
        self.assertIsNone(specimen.origin_version)
        self.assertIsNone(response.data["origin_mark"])

    def test_filter_origin_mark(self):
        def ot(version_group, version):
            group = f.make_version_group(name=version_group)
            return f.make_ot(version=f.make_version(name=version, version_group=group))

        scarlet_ot, violet_ot = ot("scarlet-violet", "scarlet"), ot(
            "the-teal-mask", "tm"
        )
        sword_ot, emerald_ot = ot("sword-shield", "sword"), ot("emerald", "emerald")
        scarlet = f.make_specimen(self.charmander, ot=scarlet_ot)
        teal_mask = f.make_specimen(self.charmander, ot=violet_ot)
        sword = f.make_specimen(self.charmander, ot=sword_ot)
        go = f.make_specimen(self.charmander, ot=scarlet_ot, is_from_go=True)
        emerald = f.make_specimen(self.charmander, ot=emerald_ot)

        def ids(value):
            response = self.client.get(
                reverse("api:specimen-list"), {"origin_mark": value}
            )
            return {s["id"] for s in response.data["results"]}

        self.assertEqual(ids("paldea"), {scarlet.pk, teal_mask.pk})
        self.assertEqual(ids("paldea,galar"), {scarlet.pk, teal_mask.pk, sword.pk})
        self.assertEqual(ids("go"), {go.pk})
        self.assertEqual(
            ids("none"), {emerald.pk, self.bulbasaur_specimen.pk}
        )  # emerald: Gen 3; bulbasaur: sem OT
        self.assertEqual(ids("galar,go"), {sword.pk, go.pk})
        self.assertEqual(ids("unknown"), set())

    def test_bulk_updates_only_given_fields(self):
        ot = f.make_ot()
        a = f.make_specimen(self.charmander, nature="bold", is_alpha=True)
        b = f.make_specimen(self.charmander, nature="bold")
        untouched = f.make_specimen(self.charmander, nature="bold")
        before = Specimen.objects.get(pk=a.pk).updated_at

        response = self.bulk(
            [a.pk, b.pk, a.pk],
            {
                "pokeball": "dive-ball",
                "ot": ot.pk,
                "captured_at": "2026-01-02",
                "is_shiny": True,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"updated": 2})
        for pk in (a.pk, b.pk):
            specimen = Specimen.objects.get(pk=pk)
            self.assertEqual(specimen.pokeball, "dive-ball")
            self.assertEqual(specimen.ot, ot)
            self.assertEqual(specimen.captured_at, date(2026, 1, 2))
            self.assertTrue(specimen.is_shiny)
            self.assertEqual(specimen.nature, "bold")  # não enviado: mantido
        self.assertTrue(Specimen.objects.get(pk=a.pk).is_alpha)
        self.assertGreater(Specimen.objects.get(pk=a.pk).updated_at, before)
        self.assertIsNone(Specimen.objects.get(pk=untouched.pk).pokeball)

    def test_bulk_ot_change_derives_origin_version(self):
        scarlet = f.make_version(
            name="scarlet", version_group=f.make_version_group(name="scarlet-violet")
        )
        with_version = f.make_ot(version=scarlet)
        specimen = f.make_specimen(self.charmander)
        kept = f.make_specimen(self.charmander, ot=with_version)

        self.bulk([specimen.pk], {"ot": with_version.pk})
        specimen.refresh_from_db()
        self.assertEqual(specimen.origin_version, scarlet)

        self.bulk([specimen.pk], {"ot": None})
        specimen.refresh_from_db()
        self.assertIsNone(specimen.origin_version)

        self.bulk([kept.pk], {"nature": "bold"})  # sem ot: jogo mantido
        kept.refresh_from_db()
        self.assertEqual(kept.origin_version, scarlet)

    def test_bulk_null_removes_value(self):
        specimen = f.make_specimen(
            self.charmander,
            pokeball="dive-ball",
            ot=f.make_ot(),
            captured_at=date(2026, 1, 2),
        )
        other = f.make_specimen(self.charmander, pokeball="dusk-ball")

        self.bulk([specimen.pk], {"pokeball": None, "ot": None, "captured_at": None})
        self.bulk([other.pk], {"pokeball": ""})

        specimen.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNone(specimen.pokeball)
        self.assertIsNone(specimen.ot)
        self.assertIsNone(specimen.captured_at)
        self.assertIsNone(other.pokeball)

    def test_bulk_rejects_invalid_requests(self):
        pk = self.bulbasaur_specimen.pk

        unknown = self.bulk([pk], {"nickname": "x", "ability": "y"})
        empty = self.bulk([pk], {})
        no_ids = self.bulk([], {"is_alpha": True})
        bad_choice = self.bulk([pk], {"nature": "sleepy"})

        for response in (unknown, empty, no_ids, bad_choice):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(unknown.data["changes"]), {"ability", "nickname"})
        self.assertEqual(
            unknown.data["changes"]["nickname"],
            ["este campo não pode ser alterado em lote."],
        )
        self.assertEqual(
            empty.data["changes"]["non_field_errors"], ["nenhuma alteração."]
        )
        self.assertIn("ids", no_ids.data)
        self.assertIn("nature", bad_choice.data["changes"])

    def test_bulk_missing_ids_changes_nothing(self):
        response = self.bulk([self.bulbasaur_specimen.pk, 998, 999], {"is_alpha": True})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["ids"], ["espécimes não encontrados: 998, 999"])
        self.assertFalse(Specimen.objects.filter(is_alpha=True).exists())

    def test_bulk_gender_validated_per_specimen(self):
        species, _, latias = f.make_full_pokemon("latias", 380)
        species.gender_rate = 8
        species.save()
        _, _, oinkologne = f.make_full_pokemon("oinkologne-female", 916)
        oinkologne.pokemon.species.gender_rate = 0  # como na base importada
        oinkologne.pokemon.species.save()
        female_only = f.make_specimen(latias, gender="genderless")
        gender_form = f.make_specimen(oinkologne)
        either = f.make_specimen(self.charmander)  # gender_rate 4

        ok = self.bulk(
            [female_only.pk, gender_form.pk, either.pk], {"gender": "female"}
        )
        conflict = self.bulk(
            [female_only.pk, gender_form.pk, either.pk], {"gender": "male"}
        )

        self.assertEqual(ok.data, {"updated": 3})
        self.assertEqual(conflict.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            conflict.data["gender"],
            ["este gênero não é possível para 2 espécime(s)."],
        )
        self.assertEqual(
            conflict.data["conflicts"],
            [
                {"id": female_only.pk, "form_name": "latias"},
                {"id": gender_form.pk, "form_name": "oinkologne-female"},
            ],
        )
        # Tudo ou nada: os três continuam fêmea.
        self.assertEqual(
            set(
                Specimen.objects.filter(
                    pk__in=[female_only.pk, gender_form.pk, either.pk]
                ).values_list("gender", flat=True)
            ),
            {"female"},
        )

    def test_options(self):
        with (
            tempfile.TemporaryDirectory() as root,
            self.settings(TYPE_SPRITES_ROOT=Path(root)),
        ):
            small = Path(root) / "generation-viii" / "sword-shield" / "small"
            small.mkdir(parents=True)
            (small / "11.png").write_bytes(b"png")  # water = 11

            response = self.client.get(reverse("api:specimen-options"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {
                "language",
                "gender",
                "nature",
                "pokeball",
                "type",
                "generation",
                "origin_mark",
            },
        )
        self.assertEqual(
            [m["value"] for m in response.data["origin_mark"]],
            [
                "game-boy",
                "kalos",
                "alola",
                "lets-go",
                "galar",
                "bdsp",
                "hisui",
                "paldea",
                "lumiose",
                "go",
                "none",
            ],
        )
        self.assertIn(
            {"value": "paldea", "label": "SV"},
            response.data["origin_mark"],
        )
        self.assertEqual(len(response.data["type"]), 18)
        self.assertIn(
            {
                "value": "water",
                "label": "Água",
                "sprite_url": "http://testserver/media/sprites/types/"
                "generation-viii/sword-shield/small/11.png",
            },
            response.data["type"],
        )
        self.assertIn(
            {"value": "fire", "label": "Fogo", "sprite_url": None},
            response.data["type"],
        )
        self.assertEqual(
            response.data["generation"][3],
            {"value": "generation-iv", "label": "Geração IV"},
        )
        self.assertIn({"value": "male", "label": "Macho"}, response.data["gender"])
        self.assertIn(
            {"value": "pt-br", "label": "Português brasileiro"},
            response.data["language"],
        )
        self.assertIn(
            {
                "value": "dream-ball",
                "label": "Dream Ball",
                "sprite_url": "http://testserver/media/sprites/items/dream-ball.png",
            },
            response.data["pokeball"],
        )
        self.assertEqual(len(response.data["nature"]), 25)


class FormViewSetTests(HomeAPITestCase):
    def test_list_search_by_name(self):
        response = self.client.get(reverse("api:form-list"), {"search": "char"})

        self.assertEqual(
            [form["name"] for form in response.data["results"]], ["charmander"]
        )
        self.assertNotIn("abilities", response.data["results"][0])

    def test_list_search_by_humanized_name(self):
        f.make_full_pokemon("iron-hands", 992)

        response = self.client.get(reverse("api:form-list"), {"search": "iron hands"})

        self.assertEqual(
            [form["name"] for form in response.data["results"]], ["iron-hands"]
        )

    def test_list_follows_national_dex_not_pokeapi_order(self):
        # Como o Annihilape: `order` da PokéAPI no fim, espécie no meio.
        PokemonForm.objects.filter(pk=self.bulbasaur.pk).update(order=1000)
        # Forma regional: `order` alto, mas fica junto da espécie.
        regional = f.make_form(
            self.bulbasaur.pokemon, name="bulbasaur-regional", form_order=2, order=999
        )

        response = self.client.get(reverse("api:form-list"))

        self.assertEqual(
            [form["id"] for form in response.data["results"]],
            [self.bulbasaur.pk, regional.pk, self.charmander.pk, self.squirtle.pk],
        )

    def test_retrieve_detail(self):
        f.make_shinylock(self.bulbasaur)

        # Sem o arquivo do ícone (como no CI): sprite_url nulo.
        with (
            tempfile.TemporaryDirectory() as root,
            self.settings(TYPE_SPRITES_ROOT=Path(root)),
        ):
            response = self.client.get(
                reverse("api:form-detail", args=[self.bulbasaur.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["types"], [{"slot": 1, "type": "grass", "sprite_url": None}]
        )
        self.assertEqual(
            [a["ability"] for a in response.data["abilities"]],
            ["overgrow", "chlorophyll"],
        )
        self.assertTrue(response.data["is_shinylocked"])
        self.assertFalse(response.data["is_distro_only"])

    def test_retrieve_detail_type_sprite(self):
        with (
            tempfile.TemporaryDirectory() as root,
            self.settings(TYPE_SPRITES_ROOT=Path(root)),
        ):
            small = Path(root) / "generation-viii" / "sword-shield" / "small"
            small.mkdir(parents=True)
            (small / "12.png").write_bytes(b"png")  # grass = 12

            response = self.client.get(
                reverse("api:form-detail", args=[self.bulbasaur.pk])
            )

        self.assertEqual(
            response.data["types"][0]["sprite_url"],
            "http://testserver/media/sprites/types/generation-viii/sword-shield/"
            "small/12.png",
        )

    def test_type_sprite_url_unknown_type(self):
        self.assertIsNone(type_sprite_url(None, "not-a-type"))


class TrainerViewSetTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_user("ash"))

    def test_list_and_create(self):
        version = f.make_version(name="scarlet")

        created = self.client.post(
            reverse("api:trainer-list"),
            {"name": "Ash", "trainer_id": "123456", "version": "scarlet"},
            format="json",
        )
        listed = self.client.get(reverse("api:trainer-list"))

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            listed.data["results"],
            [
                {
                    "id": created.data["id"],
                    "name": "Ash",
                    "trainer_id": "123456",
                    "version": version.name,
                }
            ],
        )

    def test_duplicate_trainer_is_400(self):
        f.make_ot(name="Ash", trainer_id="123456")

        response = self.client.post(
            reverse("api:trainer-list"),
            {"name": "Ash", "trainer_id": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VersionViewSetTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_user("ash"))

    def test_list_in_release_order_without_pagination(self):
        sv = f.make_version_group(
            name="scarlet-violet", generation="generation-ix", order=20
        )
        rb = f.make_version_group(name="red-blue", generation="generation-i", order=1)
        f.make_version(name="scarlet", version_group=sv)
        f.make_version(name="red", version_group=rb)

        response = self.client.get(reverse("api:version-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "name": "red",
                    "version_group": "red-blue",
                    "generation": "generation-i",
                },
                {
                    "name": "scarlet",
                    "version_group": "scarlet-violet",
                    "generation": "generation-ix",
                },
            ],
        )

    def test_is_read_only(self):
        response = self.client.post(
            reverse("api:version-list"), {"name": "x"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
