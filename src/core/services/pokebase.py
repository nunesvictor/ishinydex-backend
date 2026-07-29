import os
from urllib.parse import urlparse, urlunparse

import requests

_original_get = requests.get


def _custom_get(url, *args, **kwargs):
    if "pokeapi.co" in url:
        netloc = os.getenv("POKEAPI_HOST", None)

        if netloc:
            url = urlunparse(urlparse(url)._replace(netloc=netloc, scheme="http"))

    return _original_get(url, *args, **kwargs)


requests.get = _custom_get

import pokebase as pb  # noqa: E402

__all__ = ["pb"]
