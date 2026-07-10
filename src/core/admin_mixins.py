from typing import Literal

from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

import pokebase as pb

from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

from .utils import get_home_sprite, get_media_sprite_url

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

        return get_media_sprite_url(sprite), type

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

        return format_html(
            "<img height='96' src='{}' alt='{}' class='pokemon-sprite {}' />",
            get_media_sprite_url(get_home_sprite(obj, opt)),
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
