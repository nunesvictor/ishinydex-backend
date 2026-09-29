import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from api.serializers.home import type_sprite_url
from core.tests import factories as f
from home.models import PersonalDex, Slot, Specimen


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
                "first_box": {
                    "id": self.other_box.pk,
                    "name": "HOME 3",
                    "position": self.other_box.position,
                },
            },
        )
        self.assertEqual(PersonalDex.objects.count(), 1)

    def test_preview_without_space(self):
        self.set_slot(self.other_box, 0, 0, self.charmander, dex=self.dex)

        response = self.client.get(reverse("api:personal-dex-preview"))

        self.assertFalse(response.data["enough_space"])
        self.assertIsNone(response.data["first_box"])
        self.assertEqual(response.data["largest_free_run"], 0)

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
                    "PersonalDex: ele precisa de 1, e a maior sequência livre "
                    "tem 0."
                ]
            },
        )
        self.assertFalse(PersonalDex.objects.filter(name="Living Dex").exists())

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


class SlotViewSetTests(HomeAPITestCase):
    def test_list_by_box_returns_all_slots_without_pagination(self):
        with self.assertNumQueries(1):
            response = self.client.get(reverse("api:slot-list"), {"box": self.box1.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 30)
        self.assertEqual(
            [(s["row"], s["col"]) for s in response.data[:3]],
            [(0, 0), (0, 1), (0, 2)],
        )

    def test_slot_representation(self):
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

    def test_options(self):
        response = self.client.get(reverse("api:specimen-options"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data), {"language", "gender", "nature", "pokeball"}
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
