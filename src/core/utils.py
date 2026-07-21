import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

type SpriteOption = Literal["front_default", "front_shiny"]
type SpriteModel = Pokemon | PokemonForm | Slot


_SPRITE_BASE_URL = f"{settings.MEDIA_URL}/sprites/pokemon/other/home/"


def get_pokemon_and_form(obj: SpriteModel) -> tuple[Pokemon, PokemonForm]:
    if isinstance(obj, Slot):
        if not hasattr(obj, "form") or obj.form is None:
            raise TypeError(
                _("%s doesn't have a PokemonForm associate with it." % type(obj))
            )

        return get_pokemon_and_form(obj.form)

    if isinstance(obj, PokemonForm):
        return (obj.pokemon, obj)

    if isinstance(obj, Pokemon):
        form = obj.forms.filter(is_default=True).first()

        if not form:
            raise TypeError(_("Couldn't find a default form for Pokemon: %s" % obj))

        return (obj, form)

    raise ValueError(_("Could't retrive a form from %s object" % type(obj)))


def get_sprite(obj: SpriteModel, opt: SpriteOption = "front_default") -> Path:
    def _female_path(pokemon: Pokemon, form: PokemonForm) -> str:
        if pokemon.species.has_gender_differences and form.name.endswith("-female"):
            return "female"

        return ""

    def _shiny_path(opt: SpriteOption) -> str:
        if opt == "front_shiny":
            return "shiny"

        return ""

    def _imagefile_path(pokemon: Pokemon) -> str:
        return f"{pokemon.pokeapi_id}.png"

    pokemon, form = get_pokemon_and_form(obj)
    sprite_base_path = Path(_SPRITE_BASE_URL)
    sprite_path = sprite_base_path

    sprite_path /= _shiny_path(opt)
    sprite_path /= _female_path(pokemon, form)
    sprite_path /= _imagefile_path(pokemon)

    if not Path(settings.BASE_DIR / sprite_path.as_posix().lstrip("/")).exists():
        return sprite_base_path / "0.png"

    return sprite_path


def get_sprite_html(obj: SpriteModel, opt: SpriteOption = "front_default", **kwargs):
    classes = kwargs.get("classes", [])
    width = kwargs.get("width", 96)
    height = kwargs.get("height", 96)
    _, form = get_pokemon_and_form(obj)

    return format_html(
        '<img src="{url}"'
        'class="{extra_classes}"'
        'alt="{obj}" height="{height}" width="{width}" />',
        url=get_sprite(obj, opt),
        extra_classes=" ".join(classes),
        obj=form.name,
        height=height,
        width=width,
    )


def get_media_sprite_url(sprite: str) -> str:
    if not re.search(
        r"https://raw\.githubusercontent\.com/PokeAPI/sprites/master/sprites"
        r"/(?:pokemon|types)/(?:[^/]+/)*\d+\.(?:png|jpg|jpeg|webp)",
        sprite,
    ):
        return sprite

    old_url = urlparse(sprite)

    return urlunparse(
        old_url._replace(
            netloc="",
            scheme="",
            path=old_url.path.replace(
                "/PokeAPI/sprites/master/sprites",
                settings.SPRITES_URL,
            ),
        )
    )
