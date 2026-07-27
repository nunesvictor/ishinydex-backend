import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.typing import SpriteObject, SpriteOption
from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

_SPRITE_BASE_URL = f"{settings.MEDIA_URL}/sprites/pokemon/other/home/"


def get_pokemon_and_form(obj: SpriteObject) -> tuple[Pokemon, PokemonForm]:
    if isinstance(obj, Slot):
        if not hasattr(obj, "form") or obj.form is None:
            raise TypeError(
                _("%s doesn't have a PokemonForm associate with it." % type(obj))
            )

        return get_pokemon_and_form(obj.form)

    if isinstance(obj, PokemonForm):
        if not obj.pokemon:
            raise ValueError()
        return (obj.pokemon, obj)

    if isinstance(obj, Pokemon):
        form = obj.forms.filter(is_default=True).first()

        if not form:
            raise TypeError(_("Couldn't find a default form for Pokemon: %s" % obj))

        return (obj, form)

    raise ValueError(_("Could't retrive a form from %s object" % type(obj)))


def get_sprite(obj: SpriteObject, opt: SpriteOption = "front_default") -> Path:
    def _shiny_path(opt: SpriteOption) -> str:
        if opt == "front_shiny":
            return "shiny"

        return ""

    def _female_path(pokemon: Pokemon, form: PokemonForm) -> str:
        if pokemon.species.has_gender_differences and form.name.endswith("-female"):
            return "female"

        return ""

    def _imagefile_path(base_path: Path, pokemon: Pokemon, form: PokemonForm) -> str:
        is_female_sprite = _female_path(pokemon, form) == "female"
        filename = f"{pokemon.pokeapi_id}.png"

        if pokemon.name != form.name and not is_female_sprite:
            suffix = form.name.removeprefix(pokemon.name)

            if Path(base_path / f"{pokemon.pokeapi_id}{suffix}.png").exists():
                filename = f"{pokemon.pokeapi_id}{suffix}.png"

        return filename

    sprite_base_path = Path(_SPRITE_BASE_URL)
    sprite_path = sprite_base_path

    try:
        pokemon, form = get_pokemon_and_form(obj)
        print(pokemon, form)

        sprite_path /= _shiny_path(opt)
        sprite_path /= _female_path(pokemon, form)
        sprite_path /= _imagefile_path(sprite_path, pokemon, form)
    except TypeError:
        return sprite_base_path / "0.png"

    if not Path(settings.BASE_DIR / sprite_path.as_posix().lstrip("/")).exists():
        return sprite_base_path / "0.png"

    return sprite_path


def get_sprite_html(obj: SpriteObject, opt: SpriteOption = "front_default", **kwargs):
    classes = kwargs.get("classes", [])
    width = kwargs.get("width", 96)
    height = kwargs.get("height", 96)

    sprite_url = get_sprite(obj, opt)

    return format_html(
        '<img src="{img_src}"'
        'class="{img_class}"'
        'alt="{img_alt}" height="{img_height}" width="{img_width}" />',
        img_src=sprite_url,
        img_class=" ".join(classes),
        img_alt=obj.__repr__(),
        img_height=height,
        img_width=width,
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
