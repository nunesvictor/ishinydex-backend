import os

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from core.tests import factories as f


class AuthTokenTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ash", password="pikachu123")

    def test_obtain_token(self):
        response = self.client.post(
            reverse("api:auth-token"),
            {"username": "ash", "password": "pikachu123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data, {"token": Token.objects.get(user=self.user).key}
        )

    def test_obtain_token_with_wrong_password(self):
        response = self.client.post(
            reverse("api:auth-token"),
            {"username": "ash", "password": "wrong"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_obtain_token_ignores_session_cookie(self):
        # O navegador envia o cookie de sessão do admin junto com o login do
        # frontend (mesma origem); o endpoint não pode exigir CSRF por causa dele.
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post(
            reverse("api:auth-token"),
            {"username": "ash", "password": "pikachu123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_token_authenticates_requests(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(reverse("api:personal-dex-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AuthenticationRequiredTests(APITestCase):
    def test_all_endpoints_return_401_without_token(self):
        dex = f.make_personal_dex()
        slot = f.make_box().slots.get(row=0, col=0)
        form = f.make_full_pokemon("bulbasaur", 1)[2]
        specimen = f.make_specimen(form)

        requests = [
            ("get", reverse("api:pokemon-list")),
            ("get", reverse("api:personal-dex-list")),
            ("get", reverse("api:personal-dex-detail", args=[dex.pk])),
            ("get", reverse("api:personal-dex-boxes", args=[dex.pk])),
            ("get", reverse("api:slot-list")),
            ("get", reverse("api:slot-detail", args=[slot.pk])),
            ("post", reverse("api:slot-deposit", args=[slot.pk])),
            ("post", reverse("api:slot-withdraw", args=[slot.pk])),
            ("get", reverse("api:specimen-list")),
            ("post", reverse("api:specimen-list")),
            ("get", reverse("api:specimen-detail", args=[specimen.pk])),
            ("patch", reverse("api:specimen-detail", args=[specimen.pk])),
            ("delete", reverse("api:specimen-detail", args=[specimen.pk])),
            ("get", reverse("api:specimen-options")),
            ("get", reverse("api:form-list")),
            ("get", reverse("api:form-detail", args=[form.pk])),
            ("get", reverse("api:trainer-list")),
            ("post", reverse("api:trainer-list")),
            ("get", reverse("api:version-list")),
        ]

        for method, url in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertEqual(response["WWW-Authenticate"], "Token")


class CorsTests(APITestCase):
    @override_settings(CORS_ALLOWED_ORIGINS=["https://app.example.com"])
    def test_cors_header_for_configured_origin(self):
        response = self.client.options(
            reverse("api:auth-token"),
            HTTP_ORIGIN="https://app.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )

        self.assertEqual(
            response["Access-Control-Allow-Origin"], "https://app.example.com"
        )
        self.assertIn("authorization", response["Access-Control-Allow-Headers"])

    @override_settings(
        CORS_ALLOWED_ORIGINS=["https://app.example.com"],
        CORS_ALLOWED_ORIGIN_REGEXES=[],
    )
    def test_no_cors_header_for_other_origins(self):
        response = self.client.get(
            reverse("api:pokemon-list"), HTTP_ORIGIN="https://evil.example.com"
        )

        self.assertNotIn("Access-Control-Allow-Origin", response)


class SchemaTests(APITestCase):
    def test_schema_is_valid_without_warnings(self):
        # --fail-on-warn: qualquer warning na geração lança SchemaGenerationError
        call_command("spectacular", validate=True, fail_on_warn=True, file=os.devnull)

    def test_schema_and_docs_are_public(self):
        self.assertEqual(
            self.client.get(reverse("schema")).status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            self.client.get(reverse("docs")).status_code, status.HTTP_200_OK
        )
