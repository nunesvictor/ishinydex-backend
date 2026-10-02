from datetime import timedelta
from typing import cast

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.tests import factories as f
from core.tests.mixins import TempSpritesMixin
from home.admin import BoxAdmin
from home.admin_filters import RegistrationStatusFilter
from home.models import Box, Slot, Specimen


class AdminTestCase(TempSpritesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser("admin", "a@a.com", "pw")
        self.client.force_login(self.user)

        _, _, self.form = f.make_full_pokemon("bulbasaur", 1, abilities=("overgrow",))
        self.add_sprite("pokemon/1.png")
        self.add_sprite("pokemon/shiny/1.png")
        self.add_sprite("pokemon/other/home/1.png")
        self.add_sprite("pokemon/other/home/shiny/1.png")

        self.box = f.make_box(name="HOME 1")
        self.slot = self.box.slots.get(row=0, col=0)
        self.slot.form = self.form
        self.slot.save()


class RegistrationStatusFilterTests(TestCase):
    def setUp(self):
        _, _, form = f.make_full_pokemon("bulbasaur", 1)
        self.slots = list(f.make_box().slots.all()[:2])
        self.slots[0].specimen = f.make_specimen(form)
        self.slots[0].save()

    def _qs(self, value):
        params = {"is_registered": [value]} if value is not None else {}
        request = RequestFactory().get("/")
        flt = RegistrationStatusFilter(request, params, Slot, site._registry[Slot])
        return flt.queryset(request, Slot.objects.all())

    def test_registered(self):
        self.assertQuerySetEqual(self._qs("1"), [self.slots[0]])

    def test_unregistered(self):
        self.assertEqual(self._qs("0").count(), 29)

    def test_no_value(self):
        self.assertEqual(self._qs(None).count(), 30)

    def test_invalid_value_is_ignored(self):
        """Regressão: valor não numérico gerava erro 500 (int())."""
        self.assertEqual(self._qs("abc").count(), 30)


class BoxAdminTests(AdminTestCase):
    def test_changelist_columns(self):
        self.slot.personal_dex = f.make_personal_dex(self.form)
        self.slot.save()
        box_admin = cast(BoxAdmin, site._registry[Box])

        self.assertTrue(box_admin.is_schema_configured(self.box))
        self.assertFalse(box_admin.is_schema_filled_out(self.box))
        self.assertEqual(box_admin.empty_slots(self.box), "1")

        self.slot.specimen = f.make_specimen(self.form)
        self.slot.save()

        self.assertTrue(box_admin.is_schema_filled_out(self.box))
        self.assertEqual(box_admin.empty_slots(self.box), "-")

    def test_unconfigured_box(self):
        box_admin = cast(BoxAdmin, site._registry[Box])
        other = f.make_box()

        self.assertFalse(box_admin.is_schema_configured(other))
        self.assertFalse(box_admin.is_schema_filled_out(other))

    def test_views(self):
        response = self.client.get(reverse("admin:home_box_changelist"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("admin:home_box_change", args=[self.box.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/media/sprites/pokemon/other/home/1.png")

        response = self.client.get(reverse("admin:home_box_add"))
        self.assertEqual(response.status_code, 403)


class PersonalDexAdminTests(AdminTestCase):
    def setUp(self):
        super().setUp()
        self.dex = f.make_personal_dex(self.form, name="Living")
        Slot.objects.filter(pk=self.slot.pk).update(personal_dex=self.dex)

    def assert_slot_freed(self):
        self.slot.refresh_from_db()
        self.assertIsNone(self.slot.form)
        self.assertIsNone(self.slot.personal_dex)

    def test_delete_view_frees_slots(self):
        response = self.client.post(
            reverse("admin:home_personaldex_delete", args=[self.dex.pk]),
            {"post": "yes"},
        )

        self.assertEqual(response.status_code, 302)
        self.assert_slot_freed()

    def test_delete_action_frees_slots(self):
        response = self.client.post(
            reverse("admin:home_personaldex_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [self.dex.pk],
                "post": "yes",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assert_slot_freed()


class SlotAdminTests(AdminTestCase):
    def test_changelist_shows_grid_of_first_box_by_default(self):
        f.make_box(name="HOME 2")

        response = self.client.get(reverse("admin:home_slot_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_box_id"], str(self.box.pk))
        self.assertEqual(len(response.context["grid_slots"]), 30)
        self.assertEqual(response.context["cl"].result_count, 30)
        self.assertFalse(response.context["is_filtered"])

    def test_changelist_selected_box(self):
        other = f.make_box(name="HOME 2")

        response = self.client.get(
            reverse("admin:home_slot_changelist"), {"box__id__exact": other.pk}
        )

        self.assertEqual(response.context["selected_box_id"], str(other.pk))
        self.assertTrue(
            all(s.box_id == other.pk for s in response.context["grid_slots"])
        )

    def test_filtered_changelist_searches_all_boxes(self):
        other = f.make_box(name="HOME 2")
        slot = other.slots.earliest("position")
        slot.form = self.form
        slot.save()

        response = self.client.get(
            reverse("admin:home_slot_changelist"), {"q": "bulbasaur"}
        )

        self.assertTrue(response.context["is_filtered"])
        self.assertNotIn("grid_slots", response.context)
        self.assertEqual(response.context["cl"].result_count, 2)

    def test_empty_search_is_not_a_filter(self):
        response = self.client.get(reverse("admin:home_slot_changelist"), {"q": ""})

        self.assertFalse(response.context["is_filtered"])

    def test_panels_group_boxes_by_30(self):
        for _ in range(30):
            f.make_box()

        response = self.client.get(reverse("admin:home_slot_changelist"))

        panels = response.context["panels"]
        self.assertEqual([p["label"] for p in panels], ["Boxes 1-30", "Boxes 31-31"])

    def test_change_view(self):
        response = self.client.get(
            reverse("admin:home_slot_change", args=[self.slot.pk]),
            {"box__id__exact": self.box.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_box_id"], str(self.box.pk))
        self.assertFalse(response.context["show_save_and_move_on"])

    def test_move_on_button_when_there_are_later_slots_with_form(self):
        later = self.box.slots.get(row=0, col=1)
        later.form = self.form
        later.save()

        response = self.client.get(
            reverse("admin:home_slot_change", args=[self.slot.pk])
        )

        self.assertTrue(response.context["show_save_and_move_on"])

    def _post_change(self, slot, headers=None, **extra):
        data = {"form": slot.form_id or "", "specimen": "", "personal_dex": ""}
        return self.client.post(
            reverse("admin:home_slot_change", args=[slot.pk]),
            data | extra,
            headers=headers,
        )

    def test_save_and_move_on_goes_to_next_slot(self):
        next_slot = self.box.slots.get(row=0, col=1)

        response = self._post_change(
            self.slot, _moveon="1", _box_id_filter=str(self.box.pk)
        )

        self.assertRedirects(
            response,
            reverse("admin:home_slot_change", args=[next_slot.pk])
            + f"?box__id__exact={self.box.pk}",
            fetch_redirect_response=False,
        )

    def test_save_and_move_on_crosses_to_next_box(self):
        next_box = f.make_box(name="HOME 2")
        last_slot = self.box.slots.get(row=4, col=5)

        response = self._post_change(last_slot, _moveon="1")

        self.assertRedirects(
            response,
            reverse(
                "admin:home_slot_change", args=[next_box.slots.earliest("position").pk]
            ),
            fetch_redirect_response=False,
        )

    def test_save_and_move_on_at_last_slot_returns_to_changelist(self):
        last_slot = self.box.slots.get(row=4, col=5)

        response = self._post_change(last_slot, _moveon="1")

        self.assertRedirects(
            response,
            reverse("admin:home_slot_changelist"),
            fetch_redirect_response=False,
        )

    def test_save_returns_to_changelist_keeping_box(self):
        response = self._post_change(self.slot, _box_id_filter=str(self.box.pk))

        self.assertRedirects(
            response,
            reverse("admin:home_slot_changelist") + f"?box__id__exact={self.box.pk}",
            fetch_redirect_response=False,
        )

    def test_box_is_recovered_from_referer(self):
        response = self._post_change(
            self.slot,
            headers={
                "referer": f"http://testserver/admin/?box__id__exact={self.box.pk}"
            },
        )

        self.assertRedirects(
            response,
            reverse("admin:home_slot_changelist") + f"?box__id__exact={self.box.pk}",
            fetch_redirect_response=False,
        )

    def test_rejects_specimen_of_other_form(self):
        _, _, other_form = f.make_full_pokemon("charmander", 4)
        specimen = f.make_specimen(other_form)

        response = self._post_change(self.slot, specimen=specimen.pk)

        self.assertEqual(response.status_code, 200)
        self.assertIn("specimen", response.context["adminform"].form.errors)

    def test_changelist_with_invalid_filter_value(self):
        response = self.client.get(
            reverse("admin:home_slot_changelist"), {"is_registered": "abc"}
        )

        self.assertEqual(response.status_code, 200)

    def test_add_is_disabled(self):
        response = self.client.get(reverse("admin:home_slot_add"))

        self.assertEqual(response.status_code, 403)


class SpecimenAdminTests(AdminTestCase):
    def test_changelist(self):
        f.make_specimen(self.form, is_shiny=True, gender="female")

        response = self.client.get(reverse("admin:home_specimen_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/media/sprites/pokemon/other/home/shiny/1.png")
        self.assertContains(response, "♀️")

    def test_changelist_filter_by_origin_mark(self):
        sv = f.make_version_group(name="scarlet-violet")
        ot = f.make_ot(version=f.make_version(name="scarlet", version_group=sv))
        paldea = f.make_specimen(self.form, ot=ot, nickname="Paldeano")
        f.make_specimen(self.form, nickname="Sem marca")

        response = self.client.get(
            reverse("admin:home_specimen_changelist"), {"origin_mark": "paldea"}
        )
        unfiltered = self.client.get(reverse("admin:home_specimen_changelist"))

        self.assertEqual(list(response.context["cl"].queryset), [paldea])
        self.assertEqual(unfiltered.context["cl"].queryset.count(), 2)

    def test_add_view_initial_from_querystring(self):
        dex = f.make_personal_dex(is_shiny_dex=True)

        response = self.client.get(
            reverse("admin:home_specimen_add"),
            {"form_id": self.form.pk, "personal_dex_id": dex.pk},
        )

        form = response.context["adminform"].form
        self.assertEqual(form.initial["form"], str(self.form.pk))
        self.assertTrue(form.initial["is_shiny"])

    def test_popup_uses_compact_fields_and_no_inlines(self):
        response = self.client.get(reverse("admin:home_specimen_add"), {"_popup": "1"})

        fields = response.context["adminform"].form.fields
        self.assertNotIn("nickname", fields)
        self.assertNotIn("language", fields)
        self.assertEqual(response.context["inline_admin_formsets"], [])

        # O popup não pode esvaziar os inlines das próximas requisições.
        response = self.client.get(reverse("admin:home_specimen_add"))
        self.assertEqual(len(response.context["inline_admin_formsets"]), 1)

    def test_change_view(self):
        specimen = f.make_specimen(self.form)

        response = self.client.get(
            reverse("admin:home_specimen_change", args=[specimen.pk])
        )

        self.assertEqual(response.status_code, 200)


class SpecimenBulkUpdateViewTests(AdminTestCase):
    url_name = "admin:home_specimen_bulk_update"

    def setUp(self):
        super().setUp()
        self.specimens = [f.make_specimen(self.form) for _ in range(3)]

    def test_get(self):
        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["title"], "Specimen Bulk Update")

    def test_requires_staff(self):
        self.client.logout()

        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, 302)

    def test_updates_only_filled_fields_of_selected_specimens(self):
        selected = self.specimens[:2]

        response = self.client.post(
            reverse(self.url_name),
            {
                "specimens": [s.pk for s in selected],
                "is_shiny": "true",
                "nature": "bold",
                "language": "",
                "gender": "",
            },
        )

        self.assertRedirects(response, reverse(self.url_name))
        self.assertEqual(
            list(Specimen.objects.order_by("pk").values_list("is_shiny", "nature")),
            [(True, "bold"), (True, "bold"), (False, "hardy")],
        )
        messages = [m for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level_tag, "success")

    def test_changing_ot_derives_origin_version(self):
        red = f.make_version(name="red")
        ot = f.make_ot(version=red)

        self.client.post(
            reverse(self.url_name),
            {"specimens": [self.specimens[0].pk], "ot": ot.pk},
        )

        self.assertEqual(
            list(
                Specimen.objects.order_by("pk").values_list("origin_version", flat=True)
            ),
            [red.pk, None, None],
        )

    def test_updates_updated_at_of_selected_specimens(self):
        """``update()`` não aciona o ``auto_now``: a view atualiza à parte."""
        old = timezone.now() - timedelta(days=30)
        Specimen.objects.update(updated_at=old)
        selected, untouched = self.specimens[0], self.specimens[1]

        self.client.post(
            reverse(self.url_name),
            {"specimens": [selected.pk], "pokeball": "dive-ball"},
        )

        selected.refresh_from_db()
        untouched.refresh_from_db()
        self.assertEqual(selected.pokeball, "dive-ball")
        self.assertGreater(selected.updated_at, old)
        self.assertEqual(untouched.updated_at, old)

    def test_can_revert_to_default_values(self):
        """Regressão: não era possível voltar para hardy/male/não-shiny."""
        Specimen.objects.update(nature="bold", gender="female", is_shiny=True)

        self.client.post(
            reverse(self.url_name),
            {
                "specimens": [s.pk for s in self.specimens],
                "nature": "hardy",
                "gender": "male",
                "is_shiny": "false",
            },
        )

        self.assertEqual(
            set(Specimen.objects.values_list("nature", "gender", "is_shiny")),
            {("hardy", "male", False)},
        )

    def test_no_fields_filled_warns(self):
        response = self.client.post(
            reverse(self.url_name),
            {"specimens": [self.specimens[0].pk]},
            follow=True,
        )

        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level_tag, "warning")


class DevEnvironmentAdminTests(AdminTestCase):
    """Com DEBUG=True o admin se identifica como DEV (título, cabeçalho e
    cor); com DEBUG=False fica como o padrão do Django."""

    def get_index(self):
        return self.client.get(reverse("admin:index"))

    @override_settings(DEBUG=True)
    def test_dev_marks_title_header_and_color(self):
        response = self.get_index()

        self.assertTrue(response.context["is_dev_environment"])
        self.assertContains(response, "(DEV)</title>", html=False)
        self.assertContains(response, 'title="ambiente de desenvolvimento">(DEV)')
        self.assertContains(response, "--header-bg: #b45309")

    @override_settings(DEBUG=False)
    def test_production_is_unchanged(self):
        response = self.get_index()

        self.assertFalse(response.context["is_dev_environment"])
        self.assertNotContains(response, "(DEV)")
        self.assertNotContains(response, "--header-bg: #b45309")

    @override_settings(DEBUG=True)
    def test_dev_also_on_custom_admin_pages(self):
        response = self.client.get(reverse("admin:home_specimen_bulk_update"))

        self.assertContains(response, "(DEV)</title>", html=False)
