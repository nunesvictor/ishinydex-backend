from django import template

from core.utils import get_home_sprite, get_media_sprite_url
from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

type SpriteModel = Pokemon | PokemonForm | Slot


register = template.Library()


@register.simple_tag
def get_sprite_url(obj: SpriteModel) -> str:
    is_shiny = obj.specimen and obj.specimen.is_shiny

    if isinstance(obj, Slot):
        if not obj.form:
            return ""

        obj = obj.form

    return get_media_sprite_url(
        get_home_sprite(obj, "front_shiny" if is_shiny else "front_default")
    )
