from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _

import pokebase as pb

from home.models import Slot
from pokedex.models import Pokemon, PokemonForm


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

    def render_sprite(self, obj: Pokemon | PokemonForm | Slot, opt="front_default"):
        if isinstance(obj, Slot) and obj.form:
            obj = obj.form

        sprite = obj.sprites.get(opt, None)

        if isinstance(obj, Pokemon):
            sprite = obj.sprites.get("other", {}).get("home", {}).get(opt, None)

        return format_html("<img height='96' src='{}' alt='{}' />", sprite, obj.name)

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
