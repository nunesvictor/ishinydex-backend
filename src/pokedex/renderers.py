import logging
from abc import ABC, abstractmethod
from pathlib import Path

from django.conf import settings
from django.utils.html import format_html
from django.utils.module_loading import import_string

from core.typing import SpriteObject, SpriteOption
from home.choices import Pokeball
from home.models import Slot
from pokedex.models import Pokemon, PokemonForm
from pokedex.resolvers import PokemonSpriteResolver

type PokemonAndForm = tuple[Pokemon | None, PokemonForm | None]

logger = logging.getLogger(__name__)


class SpriteRenderer(ABC):
    _sprites_url = settings.SPRITES_URL

    @property
    def sprites_url(self) -> Path:
        return self._sprites_url

    @sprites_url.setter
    def sprites_url(self, url: str | Path):
        if not isinstance(url, str) and not isinstance(url, Path):
            raise AttributeError(
                "Attribute 'url' must be '%r' or '%r', found: '%s'"
                % (str, Path, type(url))
            )

        _url = Path(url)
        _path = Path(settings.BASE_DIR / _url.relative_to("/"))

        if not _path.is_dir():
            raise AttributeError("URL path is invalid: %s" % _path.as_posix())

        self._sprites_url = _url

    @abstractmethod
    def get_sprite_url(self, **kwargs) -> Path:
        pass


class ItemSpriteRenderer(SpriteRenderer):
    _sprites_url = settings.ITEM_SPRITES_URL

    def get_sprite_url(self, **kwargs):
        sprite_url = self.sprites_url / f"{self.name}.png"
        sprite_path = Path(settings.BASE_DIR / sprite_url.relative_to("/"))

        if not sprite_path.exists() or not sprite_path.is_file():
            raise FileNotFoundError(
                "%s: sprite file not found: %s" % (self.name, sprite_path.as_posix())
            )

        return sprite_url

    def __init__(self, name: str):
        self.name = name


class PokeballSpriteRenderer(ItemSpriteRenderer):
    def __init__(self, name: Pokeball):
        super().__init__(name)


class PokemonSpriteRenderer(SpriteRenderer):
    _sprites_url = settings.POKEMON_SPRITES_URL
    _is_shiny_sprite = False

    @property
    def is_shiny_sprite(self):
        return self._is_shiny_sprite

    def resolve_sprite_url(self) -> Path:
        """URL do sprite, sem verificar se o arquivo existe."""
        return self._get_sprite_resolver().resolve(self.sprites_url)

    def get_sprite_url(self, **kwargs) -> Path:
        sprite_url = self.resolve_sprite_url()
        sprite_path = Path(settings.BASE_DIR / sprite_url.relative_to("/"))
        default = kwargs.get("default")

        if not sprite_path.exists() or not sprite_path.is_file():
            sprite_error = "%r:%r sprite file not found: %s"

            if not default or not isinstance(default, Path):
                raise FileNotFoundError(
                    sprite_error % (self.pokemon, self.form, sprite_path.as_posix())
                )

            default_path = Path(settings.BASE_DIR / default.relative_to("/"))

            if not default_path.exists() or not default_path.is_file():
                raise FileNotFoundError(
                    sprite_error % (self.pokemon, self.form, default_path.as_posix())
                )

            return default

        return sprite_url

    def as_html(self, alt=None, classes=[], width=96, height=96, **kwargs):
        return format_html(
            '<img src="{img_src}"'
            'class="{img_class}"'
            'alt="{img_alt}" '
            'height="{img_height}" '
            'width="{img_width}" />',
            img_src=self.get_sprite_url(**kwargs),
            img_class=" ".join(classes),
            img_alt=alt or self.pokemon.__repr__(),
            img_height=height,
            img_width=width,
        )

    def _get_sprite_resolver(self) -> PokemonSpriteResolver:
        if not hasattr(settings, "POKEMON_SPRITE_RESOLVERS"):
            raise AttributeError(
                "'POKEMON_SPRITE_RESOLVERS' must be set in your DJANGO_SETTINGS_MODULE"
            )

        if "default" not in settings.POKEMON_SPRITE_RESOLVERS:
            raise AttributeError(
                "'POKEMON_SPRITE_RESOLVERS' must have a 'default' key set"
            )

        r_module = settings.POKEMON_SPRITE_RESOLVERS.get("default")

        if self.pokemon.name in settings.POKEMON_SPRITE_RESOLVERS:
            r_module = settings.POKEMON_SPRITE_RESOLVERS[self.pokemon.name]

        r_type = import_string(r_module)

        if not (isinstance(r_type, type) and issubclass(r_type, PokemonSpriteResolver)):
            raise ValueError(
                f"{r_type!r} must be a subclass of {PokemonSpriteResolver.__name__}."
            )

        return r_type(self.pokemon, self.form, self.is_shiny_sprite)

    def _set_shiny_sprite(self, object: SpriteObject, option: SpriteOption) -> bool:
        if option == "shiny":
            return True

        if not option and isinstance(object, Slot):
            p_dex = object.personal_dex or None
            return p_dex and p_dex.is_shiny_dex

        return False

    def _setup_pokemon_and_form(self, object: SpriteObject) -> PokemonAndForm:
        missing_related_warn = "%r doesn't have a %r instance associated with it."
        no_default_form_warn = "%r has no default form."

        if isinstance(object, Slot):
            if not hasattr(object, "form") or object.form is None:
                logger.warning(missing_related_warn, object, PokemonForm)
                return None, None

            return self._setup_pokemon_and_form(object.form)

        elif isinstance(object, PokemonForm):
            if not hasattr(object, "pokemon") or object.pokemon is None:
                logger.warning(missing_related_warn, object, Pokemon)
                return None, None

            return object.pokemon, object

        elif isinstance(object, Pokemon):
            form = object.forms.filter(is_default=True).first()

            if not form:
                logger.warning(no_default_form_warn, object)
                return None, None

            return object, form

        raise ValueError("%r: failure parsing object into %r" % (object, PokemonForm))

    def __init__(self, object: SpriteObject, option: SpriteOption = None):
        self._is_shiny_sprite = self._set_shiny_sprite(object, option)
        self.pokemon, self.form = self._setup_pokemon_and_form(object)


class HomeSpriteRenderer(PokemonSpriteRenderer):
    @property
    def sprites_url(self) -> Path:
        return super().sprites_url / "other/home"

    def __init__(self, object: SpriteObject, option: SpriteOption = None):
        super().__init__(object, option)


def get_renderer(obj_type: type[SpriteObject]) -> type[PokemonSpriteRenderer]:
    slug = obj_type.__name__.lower().strip()

    if not hasattr(settings, "SPRITE_RENDERERS"):
        raise AttributeError(
            "'SPRITE_RENDERERS' must be set in your DJANGO_SETTINGS_MODULE"
        )

    if not isinstance(settings.SPRITE_RENDERERS, dict):
        raise AttributeError("'SPRITE_RENDERERS' must be a dict")

    if "default" not in settings.SPRITE_RENDERERS:
        raise AttributeError("'SPRITE_RENDERERS' must have a 'default' key set")

    try:
        renderer = import_string(settings.SPRITE_RENDERERS[slug])
    except KeyError:
        renderer = import_string(settings.SPRITE_RENDERERS["default"])

    if not (isinstance(renderer, type) and issubclass(renderer, PokemonSpriteRenderer)):
        raise ValueError(
            f"{renderer!r} must be a subclass of {PokemonSpriteRenderer.__name__}."
        )

    return renderer
