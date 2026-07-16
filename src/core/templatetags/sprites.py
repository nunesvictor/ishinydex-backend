from django import template
from django.conf import settings

from core.utils import get_home_sprite, get_media_sprite_url
from home.models import PersonalDex, Slot, Specimen
from pokedex.models import Pokemon, PokemonForm

type SpriteModel = Pokemon | PokemonForm | Slot


register = template.Library()


@register.simple_tag
def get_sprite_url(obj: SpriteModel) -> str:
    p_dex = getattr(obj, "personal_dex", None)
    specimen = getattr(obj, "specimen", None)
    is_shiny = False

    if isinstance(specimen, Specimen):
        is_shiny = specimen.is_shiny
    elif isinstance(p_dex, PersonalDex):
        is_shiny = p_dex.is_shiny_dex

    if isinstance(obj, Slot):
        if not obj.form:
            return f"{settings.SPRITES_URL}/pokemon/other/home/0.png"

        obj = obj.form

    url = get_media_sprite_url(
        get_home_sprite(obj, f"front_{'shiny' if is_shiny else 'default'}")
    )

    return url
