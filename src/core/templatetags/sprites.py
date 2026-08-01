from django import template

from core.typing import SpriteObject, SpriteOption
from home.models import PersonalDex, Slot, Specimen
from pokedex.renderers import get_renderer

register = template.Library()


@register.simple_tag
def banner_sprite_img(obj: SpriteObject, width=96, height=96) -> str:
    SpriteRenderer = get_renderer(type(obj))
    opt: SpriteOption = "default"

    if isinstance(obj, Slot):
        if isinstance(obj.specimen, Specimen):
            opt = "shiny" if obj.specimen.is_shiny else "default"
        elif isinstance(obj.personal_dex, PersonalDex):
            opt = "shiny" if obj.personal_dex.is_shiny_dex else "default"

    extra_classes = {
        "custom-help-banner-img": True,
        "status-unregistred": (
            isinstance(obj, Slot) and not isinstance(obj.specimen, Specimen)
        ),
        "status-blinking": (
            isinstance(obj, Slot)
            and (
                not isinstance(obj.specimen, Specimen)
                or (
                    isinstance(obj.specimen, Specimen) and obj.form != obj.specimen.form
                )
            )
        ),
    }

    return SpriteRenderer(obj, opt).as_html(
        classes=[k for k, v in extra_classes.items() if v],
        height=height,
        width=width,
    )
