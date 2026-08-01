import os
from urllib.parse import urlparse, urlunparse

from django.conf import settings

import requests

logger = __import__("logging").getLogger(__name__)
_original_get = requests.get


def _custom_get(url, *args, **kwargs):
    pokeapi_url = os.getenv("POKEAPI_URL")

    if pokeapi_url and "pokeapi.co" in url:
        p_result = urlparse(pokeapi_url)

        try:
            if requests.head(pokeapi_url, timeout=3).ok:
                url = urlunparse(
                    urlparse(url)._replace(
                        netloc=p_result.netloc,
                        scheme=p_result.scheme,
                    )
                )
        except requests.RequestException:
            if settings.DEBUG:
                raise

            logger.warning(
                "POKEAPI_URL is set but the server is unreachable. Falling back "
                "to the default PokeAPI server."
            )

    return _original_get(url, *args, **kwargs)


requests.get = _custom_get

import pokebase as pb  # noqa: E402

__all__ = ["pb"]
