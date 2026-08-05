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
            if requests.head(f"{pokeapi_url}/api/v2", timeout=3).ok:
                url = urlunparse(
                    urlparse(url)._replace(
                        netloc=p_result.netloc,
                        scheme=p_result.scheme,
                    )
                )
            else:
                raise requests.RequestException(
                    "POKEAPI_URL is set but the server is unreachable. Falling back "
                    "to the default PokeAPI server."
                )
        except requests.RequestException as e:
            if settings.DEBUG:
                raise

            logger.warning(str(e))

    return _original_get(url, *args, **kwargs)


requests.get = _custom_get

import pokebase as pb  # noqa: E402

__all__ = ["pb"]
