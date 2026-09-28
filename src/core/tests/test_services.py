from unittest import mock

from django.test import SimpleTestCase, override_settings

from requests.exceptions import ConnectionError

from core.services import pokebase as service


@mock.patch.object(service, "_original_get")
class PokeApiUrlOverrideTests(SimpleTestCase):
    url = "https://pokeapi.co/api/v2/pokemon/1/"

    def test_without_env_uses_official_api(self, get_mock):
        with mock.patch.dict("os.environ", {}, clear=True):
            service._custom_get(self.url, timeout=5)

        get_mock.assert_called_once_with(self.url, timeout=5)

    def test_rewrites_host_to_local_instance(self, get_mock):
        with mock.patch.dict("os.environ", {"POKEAPI_URL": "http://localhost:8080"}):
            service._custom_get(self.url)

        get_mock.assert_called_once_with("http://localhost:8080/api/v2/pokemon/1/")

    def test_other_hosts_are_not_rewritten(self, get_mock):
        with mock.patch.dict("os.environ", {"POKEAPI_URL": "http://localhost:8080"}):
            service._custom_get("https://example.com/x")

        get_mock.assert_called_once_with("https://example.com/x")

    @override_settings(DEBUG=False)
    def test_falls_back_to_official_api_when_local_is_down(self, get_mock):
        get_mock.side_effect = [ConnectionError("down"), "ok"]

        with mock.patch.dict("os.environ", {"POKEAPI_URL": "http://localhost:8080"}):
            with self.assertLogs(service.logger, "WARNING"):
                result = service._custom_get(self.url)

        self.assertEqual(result, "ok")
        self.assertEqual(get_mock.call_args.args[0], self.url)

    @override_settings(DEBUG=True)
    def test_raises_in_debug_when_local_is_down(self, get_mock):
        get_mock.side_effect = ConnectionError("down")

        with mock.patch.dict("os.environ", {"POKEAPI_URL": "http://localhost:8080"}):
            with self.assertRaises(ConnectionError):
                service._custom_get(self.url)

    def test_requests_get_is_patched(self, _get_mock):
        import requests

        self.assertIs(requests.get, service._custom_get)
