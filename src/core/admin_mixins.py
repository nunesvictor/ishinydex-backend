import re
from typing import Literal
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _

import pokebase as pb

from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

HOME_SPRITE_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/"  # noqa

type SpriteOption = Literal["front_default", "front_shiny"]
type SpriteModel = Pokemon | PokemonForm | Slot


class CustomFieldsRendererMixin:
    def __get_type_sprite_tuple(self, type: str) -> tuple[str, str]:
        sprite = getattr(
            getattr(
                getattr(
                    pb.type_(type).sprites,
                    "generation-viii",
                ),
                "sword-shield",
            ),
            "name_icon",
        )

        return self.__convert_github_sprite_to_local(sprite), type

    def __convert_github_sprite_to_local(self, sprite: str) -> str:
        if not re.search(
            r"https://raw\.githubusercontent\.com/PokeAPI/sprites/master/sprites"
            r"/(?:pokemon|types)/(?:[^/]+/)*\d+\.(?:png|jpg|jpeg|webp)",
            sprite,
        ):
            return sprite

        new_url = urlparse(settings.SPRITES_BASE_URL)
        old_url = urlparse(sprite)

        return urlunparse(
            old_url._replace(
                netloc=new_url.netloc,
                scheme=new_url.scheme,
                path=old_url.path.replace(
                    "/PokeAPI/sprites/master/sprites",
                    new_url.path,
                ),
            )
        )

    def render_sprite(
        self,
        obj: SpriteModel,
        opt: SpriteOption = "front_default",
        is_registred: bool = False,
    ):
        if isinstance(obj, Slot):
            if not obj.form:
                return "-"

            obj = obj.form

        default_sprite = obj.sprites.get(opt, None)
        sprite = default_sprite

        if default_sprite:
            home_sprite = obj.sprites.get("other", {}).get("home", {}).get(opt, None)

            if home_sprite:
                home_sprite.split("/")[-1] = default_sprite.split("/")[-1]
            else:
                home_sprite = HOME_SPRITE_BASE_URL
                home_sprite += "shiny/" if opt == "front_shiny" else ""
                home_sprite += default_sprite.split("/")[-1]

            sprite = home_sprite

        return format_html(
            "<img height='96' src='{}' alt='{}' class='{}' />",
            self.__convert_github_sprite_to_local(sprite),
            obj.name,
            "status-unregistred" if not is_registred else "",
        )

    def render_types(self, obj: Pokemon | PokemonForm):
        if not obj.types.exists():
            return "-"

        safe_html = format_html(
            "<div style='display: flex; align-items: center;'>{}</div>",
            format_html_join(
                "\n",
                "<img height='20' src='{}' alt='{}' />",
                (self.__get_type_sprite_tuple(t.type) for t in obj.types.all()),
            ),
        )

        return safe_html

    render_sprite.short_description = _("sprite")
    render_types.short_description = _("types")
