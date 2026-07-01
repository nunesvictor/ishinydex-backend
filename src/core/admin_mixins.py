from typing import Literal

from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _

import pokebase as pb

from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

HOME_SPRITE_BASE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/"  # noqa


class CustomFieldsRendererMixin:
    def __get_type_sprite_tuple(self, type: str):
        return (
            getattr(
                getattr(
                    getattr(
                        pb.type_(type).sprites,
                        "generation-viii",
                    ),
                    "sword-shield",
                ),
                "name_icon",
            ),
            type,
        )

    def render_sprite(
        self,
        obj: Pokemon | PokemonForm | Slot,
        opt: Literal["front_default", "front_shiny"] = "front_default",
        is_registred: bool = False,
    ):
        if isinstance(obj, Slot) and obj.form:
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
            sprite,
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
