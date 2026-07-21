from django import template

from core.utils import get_sprite_html
from home.models import PersonalDex, Slot, Specimen
from pokedex.models import Pokemon, PokemonForm

type SpriteModel = Pokemon | PokemonForm | Slot

register = template.Library()


@register.simple_tag
def banner_sprite_img(obj: SpriteModel, width=96, height=96) -> str:
    personal_dex = getattr(obj, "personal_dex", None)
    is_shiny = False

    if isinstance(obj, Slot) and isinstance(obj.specimen, Specimen):
        is_shiny = obj.specimen.is_shiny
    elif isinstance(personal_dex, PersonalDex):
        is_shiny = personal_dex.is_shiny_dex

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
        classes=[k for k, v in extra_classes.items() if v],
        is_shiny=is_shiny,
        height=height,
        width=width,
    )
