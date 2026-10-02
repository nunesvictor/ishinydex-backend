from unittest import mock

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from core.admin import TimestampedAdmin
from core.tests import factories as f
from home.models import Box, Save
from pokedex.models import Move


class TimestampedAdminTests(SimpleTestCase):
    def test_timestamps_are_read_only(self):
        model_admin = site._registry[Box]

        self.assertIsInstance(model_admin, TimestampedAdmin)
        self.assertLessEqual(
            {"created_at", "updated_at"},
            set(model_admin.get_readonly_fields(RequestFactory().get("/"))),
        )


class AdminSmokeTests(TestCase):
    """Todas as telas de todos os models registrados abrem sem erro: o admin
    é só para emergência e debug, então o que importa é ele não quebrar."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "a@a.com", "pw")
        _, _, form = f.make_full_pokemon("bulbasaur", 1, types=("grass",))
        f.make_shinylock(form)
        Move.objects.create(
            name="tackle",
            pp=35,
            priority=0,
            damage_class="physical",
            generation="generation-i",
            target="selected-pokemon",
            type="normal",
        )
        f.make_box().slots.update(form=form)
        f.make_personal_dex(form)
        ot = f.make_ot(version=f.make_version(name="scarlet"))
        Save.objects.create(trainer=ot)
        f.make_specimen(form, ot=ot)

    def setUp(self):
        self.client.force_login(self.user)

    def url(self, model, view, *args):
        opts = model._meta
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_{view}", args=args)

    # Nada no admin pode depender de rede (a PokéAPI só no sync_pokeapi).
    @mock.patch("requests.get", side_effect=AssertionError("network access"))
    def test_every_admin_page_renders(self, _get):
        request = RequestFactory().get("/")
        request.user = self.user

        for model, model_admin in site._registry.items():
            with self.subTest(model=model.__name__):
                for params in ({}, {"q": "a"}):
                    response = self.client.get(self.url(model, "changelist"), params)
                    self.assertEqual(response.status_code, 200)

                if obj := model._default_manager.first():
                    response = self.client.get(self.url(model, "change", obj.pk))
                    self.assertEqual(response.status_code, 200)

                response = self.client.get(self.url(model, "add"))
                can_add = model_admin.has_add_permission(request)
                self.assertEqual(response.status_code, 200 if can_add else 403)
