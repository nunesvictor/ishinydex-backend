import gzip
import json
import shutil
import tempfile
import threading
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

import requests
from requests.adapters import HTTPAdapter

from core.services.pokeapi import LIST_LIMIT, OFFICIAL_URL, PokeAPIClient, resource_path


class ResourcePathTests(SimpleTestCase):
    def test_normalizes_urls_and_paths(self):
        for value in (
            "https://pokeapi.co/api/v2/pokemon/25/",
            "http://localhost:8080/api/v2/pokemon/25",
            "/api/v2/pokemon/25/",
            "pokemon/25",
        ):
            with self.subTest(value=value):
                self.assertEqual(resource_path(value), "pokemon/25")


def fake_response(data):
    response = mock.Mock()
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response


class LocalApiDataTests(SimpleTestCase):
    """``file://``: lê um clone do PokeAPI/api-data, sem rede nem cache."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cache_dir = Path(tempfile.mkdtemp())
        for path in (self.root, self.cache_dir):
            self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        self.write("pokemon/25", {"id": 25, "name": "pikachu"})
        self.write("pokemon/26", {"id": 26, "name": "raichu"})
        self.write(
            "pokemon",
            {"count": 2, "next": None, "results": [{"name": "pikachu"}]},
        )
        self.api = PokeAPIClient(
            base_url=f"file://{self.root}/", cache_dir=self.cache_dir
        )

    def write(self, path, data):
        file = self.root / "api" / "v2" / path / "index.json"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data))

    def test_get_list_and_get_many_read_files(self):
        with mock.patch.object(PokeAPIClient, "_fetch") as fetch:
            self.assertEqual(self.api.get("/api/v2/pokemon/25/")["name"], "pikachu")
            self.assertEqual(self.api.list("pokemon"), [{"name": "pikachu"}])
            many = self.api.get_many(["pokemon/25", "/api/v2/pokemon/26/"])

        fetch.assert_not_called()
        self.assertEqual(many["pokemon/26"]["name"], "raichu")
        self.assertEqual(list(self.cache_dir.iterdir()), [])  # sem cache

    def test_missing_resource_names_the_file(self):
        with self.assertRaisesRegex(FileNotFoundError, "pokemon/1 não existe"):
            self.api.get("pokemon/1")


class PokeAPIClientTests(SimpleTestCase):
    def setUp(self):
        self.cache_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.cache_dir, ignore_errors=True)

    def write_cache(self, path, data):
        cache_file = self.cache_dir / f"{path}.json.gz"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(gzip.compress(json.dumps(data).encode()))

    def make_client(self, **kwargs):
        kwargs.setdefault("base_url", OFFICIAL_URL)
        return PokeAPIClient(cache_dir=self.cache_dir, **kwargs)

    def patch_session(self, client, side_effect):
        session = mock.Mock()
        session.get.side_effect = side_effect
        patcher = mock.patch.object(
            PokeAPIClient, "session", new_callable=mock.PropertyMock
        )
        self.addCleanup(patcher.stop)
        patcher.start().return_value = session
        return session

    def test_get_downloads_once_and_caches_on_disk(self):
        client = self.make_client()
        session = self.patch_session(client, lambda *a, **k: fake_response({"id": 25}))

        first = client.get("https://pokeapi.co/api/v2/pokemon/25/")
        second = client.get("pokemon/25")

        self.assertEqual(first, second)
        session.get.assert_called_once_with(
            f"{OFFICIAL_URL}/api/v2/pokemon/25/", params=None, timeout=30
        )
        cache_file = self.cache_dir / "pokemon" / "25.json.gz"
        self.assertEqual(
            json.loads(gzip.decompress(cache_file.read_bytes())), {"id": 25}
        )

    def test_cache_survives_new_clients(self):
        self.write_cache("pokemon/25", {"id": 25})
        client = self.make_client()
        session = self.patch_session(client, AssertionError("network"))

        self.assertEqual(client.get("pokemon/25"), {"id": 25})
        session.get.assert_not_called()

    def test_refresh_downloads_again_only_once_per_run(self):
        self.write_cache("pokemon/25", {"id": "old"})
        client = self.make_client(refresh=True)
        session = self.patch_session(client, lambda *a, **k: fake_response({"id": 25}))

        self.assertEqual(client.get("pokemon/25"), {"id": 25})
        self.assertEqual(client.get("pokemon/25"), {"id": 25})
        self.assertEqual(session.get.call_count, 1)

    def test_list_requests_everything_in_one_call(self):
        client = self.make_client()
        results = [{"name": "bulbasaur", "url": "..."}]
        session = self.patch_session(
            client, lambda *a, **k: fake_response({"count": 1, "results": results})
        )

        self.assertEqual(client.list("pokemon-species"), results)
        self.assertEqual(client.list("pokemon-species"), results)
        session.get.assert_called_once_with(
            f"{OFFICIAL_URL}/api/v2/pokemon-species/",
            params={"limit": LIST_LIMIT},
            timeout=30,
        )

    def test_get_many_fetches_in_parallel_and_deduplicates(self):
        client = self.make_client(max_workers=4)
        session = self.patch_session(
            client, lambda url, **kwargs: fake_response({"url": url})
        )
        paths = [f"pokemon/{i}" for i in range(1, 21)] + ["pokemon/1"]

        result = client.get_many(paths)

        self.assertEqual(list(result), [f"pokemon/{i}" for i in range(1, 21)])
        self.assertEqual(session.get.call_count, 20)
        self.assertEqual(
            result["pokemon/7"], {"url": f"{OFFICIAL_URL}/api/v2/pokemon/7/"}
        )

    @override_settings(DEBUG=False)
    def test_local_instance_falls_back_to_official_api(self):
        client = self.make_client(base_url="http://localhost:8080")

        def get(url, **kwargs):
            if url.startswith("http://localhost"):
                raise requests.ConnectionError("down")
            return fake_response({"from": url})

        self.patch_session(client, get)

        with self.assertLogs("core.services.pokeapi", "WARNING"):
            data = client.get("pokemon/25")

        self.assertEqual(data, {"from": f"{OFFICIAL_URL}/api/v2/pokemon/25/"})

    @override_settings(DEBUG=True)
    def test_local_instance_failure_raises_in_debug(self):
        client = self.make_client(base_url="http://localhost:8080")
        self.patch_session(client, requests.ConnectionError("down"))

        with self.assertRaises(requests.ConnectionError):
            client.get("pokemon/25")

    def test_http_errors_are_raised_and_not_cached(self):
        client = self.make_client()
        response = mock.Mock()
        response.raise_for_status.side_effect = requests.HTTPError("404")
        self.patch_session(client, lambda *a, **k: response)

        with self.assertRaises(requests.HTTPError):
            client.get("pokemon/99999")

        self.assertFalse((self.cache_dir / "pokemon" / "99999.json.gz").exists())

    def test_session_has_retries_and_is_per_thread(self):
        client = self.make_client(retries=3)

        adapter = client.session.get_adapter("https://pokeapi.co")
        assert isinstance(adapter, HTTPAdapter)
        self.assertEqual(adapter.max_retries.total, 3)
        self.assertIn(503, adapter.max_retries.status_forcelist)

        other = []
        thread = threading.Thread(target=lambda: other.append(client.session))
        thread.start()
        thread.join()
        self.assertIsNot(other[0], client.session)

    @override_settings(POKEAPI_URL="http://pokeapi.local/")
    def test_defaults_from_settings(self):
        with override_settings(POKEAPI_CACHE_DIR=self.cache_dir):
            client = PokeAPIClient()

        self.assertEqual(client.base_url, "http://pokeapi.local")
        self.assertEqual(client.cache_dir, self.cache_dir)
