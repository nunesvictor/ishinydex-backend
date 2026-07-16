import re
from typing import Literal
from urllib.parse import urlparse, urlunparse

from django.conf import settings

from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

type SpriteOption = Literal["front_default", "front_shiny"]
type SpriteModel = Pokemon | PokemonForm | Slot


_GITHUB_SPRITES_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites"
_HOME_SPRITE_BASE_URL = f"{_GITHUB_SPRITES_BASE_URL}/master/sprites/pokemon/other/home/"


def get_home_sprite(obj: SpriteModel, opt: SpriteOption = "front_default") -> str:
    default_sprite = obj.sprites.get(opt, None)
    home_sprite = obj.sprites.get("other", {}).get("home", {}).get(opt, None)

    if home_sprite:
        home_sprite.split("/")[-1] = default_sprite.split("/")[-1]
    else:
        home_sprite = _HOME_SPRITE_BASE_URL
        home_sprite += "shiny/" if opt == "front_shiny" else ""
        home_sprite += default_sprite.split("/")[-1]

    return home_sprite


def get_media_sprite_url(sprite: str) -> str:
    if not re.search(
        r"https://raw\.githubusercontent\.com/PokeAPI/sprites/master/sprites"
        r"/(?:pokemon|types)/(?:[^/]+/)*\d+\.(?:png|jpg|jpeg|webp)",
        sprite,
    ):
        return sprite

    old_url = urlparse(sprite)

    return urlunparse(
        old_url._replace(
            netloc="",
            scheme="",
            path=old_url.path.replace(
                "/PokeAPI/sprites/master/sprites",
                settings.SPRITES_URL,
            ),
        )
    )
