from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

import pokebase as pb

from core.typing import SpriteObject, SpriteOption
from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

from .utils import get_media_sprite_url, get_sprite_html


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
        obj: SpriteObject,
        opt: SpriteOption = "front_default",
        is_registered: bool = False,
    ):
        form_specimen_mismatch = False

        if isinstance(obj, Slot):
            form_specimen_mismatch = obj.specimen and obj.specimen.form != obj.form

            if not obj.form:
                return format_html(
                    '<div style="margin: 48px auto; font-size: 150%">♻ {}</div>',
                    _("free slot"),
                )

            obj = obj.form

        classes = ["pokemon-sprite"]

        if not is_registered:
            classes.append("status-unregistred")

        if form_specimen_mismatch:
            classes.append("status-blinking")

        return get_sprite_html(obj, opt, classes=classes)

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
