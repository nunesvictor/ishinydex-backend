from django import template

from core.types import SpriteObject, SpriteOption
from core.utils import get_sprite_html
from home.models import PersonalDex, Slot, Specimen

register = template.Library()


@register.simple_tag
def banner_sprite_img(obj: SpriteObject, width=96, height=96) -> str:
    opt: SpriteOption = "front_default"

    if isinstance(obj, Slot):
        if isinstance(obj.specimen, Specimen):
            opt = "front_shiny" if obj.specimen.is_shiny else "front_default"
        elif isinstance(obj.personal_dex, PersonalDex):
            opt = "front_shiny" if obj.personal_dex.is_shiny_dex else "front_default"

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

    return get_sprite_html(
        obj,
        opt,
        classes=[k for k, v in extra_classes.items() if v],
        height=height,
        width=width,
    )
