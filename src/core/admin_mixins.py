from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from core.consts import (
    TYPES_DICT,
)
from core.typing import SpriteObject, SpriteOption
from home.models import Slot
from pokedex.models import Pokemon, PokemonForm
from pokedex.renderers import get_renderer


class CustomFieldsRendererMixin:
    def get_type_sprite(self, type_: str, *args, **kwargs) -> Path:
        gen = kwargs.get("generation", settings.TYPE_SPRITES_DEFAULT_GEN)
        game = kwargs.get("game_version", settings.TYPE_SPRITES_DEFAULT_GAME)
        type_id = TYPES_DICT[type_]

        return Path(settings.TYPE_SPRITES_URL / gen / game / f"{type_id}.png")

    @admin.display(description=_("sprite"))
    def render_sprite(self, obj: SpriteObject | None, **kwargs):
        if not obj:
            return "-"

        SpriteRenderer = kwargs.get("renderer", get_renderer(type(obj)))
        is_registered: bool = kwargs.get("is_registered", False)
        opt: SpriteOption = kwargs.get("opt", "default")

        form_specimen_mismatch = False

        if isinstance(obj, Slot):
            form_specimen_mismatch = bool(
                obj.specimen and obj.specimen.form != obj.form
            )

            if not obj.form:
                return format_html(
                    '<div style="margin: 0 auto; font-size: 130%; text-align: center;">'
                    "♻ {}"
                    "</div>",
                    _("free slot"),
                )

            obj = obj.form

        classes = ["pokemon-sprite"]

        if not is_registered:
            classes.append("status-unregistred")

        if form_specimen_mismatch:
            classes.append("status-blinking")

        return SpriteRenderer(obj, opt).as_html(classes=classes)

    @admin.display(description=_("types"))
    def render_types(self, obj: Pokemon | PokemonForm):
        if not obj.types.exists():
            return "-"

        safe_html = format_html(
            "<div style='display: flex; align-items: center;'>{}</div>",
            format_html_join(
                "\n",
                "<img height='20' src='{}' alt='{}' />",
                (
                    (self.get_type_sprite(t.type).as_posix(), t.type)
                    for t in obj.types.all()
                ),
            ),
        )

        return safe_html
