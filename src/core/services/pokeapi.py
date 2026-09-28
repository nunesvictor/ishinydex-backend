"""Cliente HTTP mínimo para a PokéAPI, com cache em disco e busca paralela.

Substitui o pokebase no sync: trabalha com os dicts crus da API (as referências
aninhadas já trazem ``name``), reaproveita conexões por thread, tem timeout e
novas tentativas automáticas, e guarda cada resposta como um arquivo JSON em
``settings.POKEAPI_CACHE_DIR`` (JSON comprimido com gzip) — depois do primeiro
download tudo roda offline.
"""

import gzip
import json
import logging
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

OFFICIAL_URL = "https://pokeapi.co"
API_PREFIX = "/api/v2/"
LIST_LIMIT = 100_000


def resource_path(url_or_path: str) -> str:
    """Normaliza URL ou caminho para a forma ``endpoint/id``.

    >>> resource_path("https://pokeapi.co/api/v2/pokemon/25/")
    'pokemon/25'
    """
    path = urlparse(url_or_path).path

    if path.startswith(API_PREFIX):
        path = path[len(API_PREFIX) :]

    return path.strip("/")


class PokeAPIClient:
    def __init__(
        self,
        base_url: str | None = None,
        cache_dir: Path | str | None = None,
        *,
        refresh: bool = False,
        timeout: float = 30,
        max_workers: int = 8,
        retries: int = 5,
    ):
        self.base_url = (base_url or settings.POKEAPI_URL).rstrip("/")
        self.cache_dir = Path(cache_dir or settings.POKEAPI_CACHE_DIR)
        self.refresh = refresh
        self.timeout = timeout
        self.max_workers = max_workers
        self.retries = retries
        self._local = threading.local()
        # Com refresh, cada recurso é baixado de novo só uma vez por execução.
        self._refreshed: set[str] = set()
        self._refreshed_lock = threading.Lock()

    # Sessões não são garantidamente thread-safe: uma por thread.
    @property
    def session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            retry = Retry(
                total=self.retries,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",),
            )
            session = requests.Session()
            session.mount("http://", HTTPAdapter(max_retries=retry))
            session.mount("https://", HTTPAdapter(max_retries=retry))
            self._local.session = session

        return self._local.session

    def _cache_file(self, path: str) -> Path:
        return self.cache_dir / f"{path}.json.gz"

    def _read_cache(self, path: str) -> dict | None:
        cache_file = self._cache_file(path)

        if self.refresh:
            with self._refreshed_lock:
                if path not in self._refreshed:
                    return None

        try:
            return json.loads(gzip.decompress(cache_file.read_bytes()))
        except FileNotFoundError:
            return None

    def _write_cache(self, path: str, data: dict) -> None:
        cache_file = self._cache_file(path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Escrita atômica: leitores concorrentes nunca veem um arquivo pela metade.
        fd, tmp = tempfile.mkstemp(dir=cache_file.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as fp:
            fp.write(gzip.compress(json.dumps(data).encode(), compresslevel=6))
        os.replace(tmp, cache_file)

        if self.refresh:
            with self._refreshed_lock:
                self._refreshed.add(path)

    def _fetch(self, url: str, params: dict | None = None) -> dict:
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _download(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{API_PREFIX}{path}/"

        try:
            return self._fetch(url, params)
        except requests.ConnectionError as error:
            if self.base_url == OFFICIAL_URL or settings.DEBUG:
                raise

            logger.warning(
                "PokéAPI em %s inacessível (%s); usando a API oficial.",
                self.base_url,
                error,
            )
            return self._fetch(f"{OFFICIAL_URL}{API_PREFIX}{path}/", params)

    def get(self, url_or_path: str) -> dict:
        path = resource_path(url_or_path)
        data = self._read_cache(path)

        if data is None:
            logger.debug("GET %s", path)
            data = self._download(path)
            self._write_cache(path, data)

        return data

    def list(self, endpoint: str) -> list[dict]:
        """Todos os itens (``name``/``url``) de um endpoint, numa só requisição."""
        endpoint = resource_path(endpoint)
        cache_key = f"{endpoint}/_list"
        data = self._read_cache(cache_key)

        if data is None:
            data = self._download(endpoint, params={"limit": LIST_LIMIT})
            self._write_cache(cache_key, data)

        return data["results"]

    def get_many(self, urls_or_paths) -> dict[str, dict]:
        """Busca vários recursos em paralelo; retorna ``{caminho: dados}``."""
        paths = list(dict.fromkeys(resource_path(u) for u in urls_or_paths))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            return dict(zip(paths, executor.map(self.get, paths)))
