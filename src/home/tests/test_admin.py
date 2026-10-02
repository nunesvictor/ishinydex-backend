from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests import factories as f
from home.models import Slot


class AdminTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", "a@a.com", "pw")
        self.client.force_login(self.user)


class PersonalDexAdminTests(AdminTestCase):
    """Apagar um dex pelo admin libera os slots, como pela API."""

    def setUp(self):
        super().setUp()
        _, _, form = f.make_full_pokemon("bulbasaur", 1)
        self.dex = f.make_personal_dex(form, name="Living")
        self.slot = f.make_box().slots.earliest("position")
        Slot.objects.filter(pk=self.slot.pk).update(form=form, personal_dex=self.dex)

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
