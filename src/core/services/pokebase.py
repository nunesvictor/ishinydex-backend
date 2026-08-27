import os
from urllib.parse import urlparse, urlunparse

from django.conf import settings

import requests
from requests.exceptions import ConnectionError

logger = __import__("logging").getLogger(__name__)
_original_get = requests.get


def _custom_get(url, *args, **kwargs):
    pokeapi_url = os.getenv("POKEAPI_URL")

    if pokeapi_url and "pokeapi.co" in url:
        p_result = urlparse(pokeapi_url)

        custom_url = urlunparse(
            urlparse(url)._replace(
                netloc=p_result.netloc,
                scheme=p_result.scheme,
            )
        )

        try:
            return _original_get(custom_url, *args, **kwargs)
        except ConnectionError as e:
            if settings.DEBUG:
                raise

            logger.warning(
                "POKEAPI_URL está configurada (%s), mas o servidor está inacessível. "
                "Utilizando o servidor oficial da PokeAPI. Erro: %s",
                pokeapi_url,
                e,
            )

    return _original_get(url, *args, **kwargs)


requests.get = _custom_get

import pokebase as pb  # noqa: E402

__all__ = ["pb"]
