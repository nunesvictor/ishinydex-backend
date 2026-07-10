from django import template

from core.utils import get_home_sprite, get_media_sprite_url
from home.models import PersonalDex, Slot, Specimen
from pokedex.models import Pokemon, PokemonForm

type SpriteModel = Pokemon | PokemonForm | Slot


register = template.Library()


@register.simple_tag
def get_sprite_url(obj: SpriteModel) -> str:
    p_dex = getattr(obj, "personal_dex", None)
    specimen = getattr(obj, "specimen", None)
    is_shiny = bool(
        (isinstance(specimen, Specimen) and specimen.is_shiny)
        or (isinstance(p_dex, PersonalDex) and p_dex.is_shiny_dex)
    )

    if isinstance(obj, Slot):
        if not obj.form:
            return ""

        obj = obj.form

    return get_media_sprite_url(
        get_home_sprite(obj, f"front_{'shiny' if is_shiny else 'default'}")
    )
