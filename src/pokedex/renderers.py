import logging
from abc import ABCMeta, abstractmethod
from pathlib import Path

from django.conf import settings
from django.utils.html import format_html

from core.typing import SpriteObject, SpriteOption
from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

type PokemonAndForm = tuple[Pokemon | None, PokemonForm | None]


logger = logging.getLogger(__name__)


class PokemonSpriteRenderer(metaclass=ABCMeta):
    _sprites_url = settings.POKEMON_SPRITES_URL
    _is_shiny_sprite = False

    @property
    def is_shiny_sprite(self):
        return self._is_shiny_sprite

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

    def as_html(self, alt: str = None, classes: list[str] = [], width=96, height=96):
        return format_html(
            '<img src="{img_src}"'
            'class="{img_class}"'
            'alt="{img_alt}" '
            'height="{img_height}" '
            'width="{img_width}" />',
            img_src=self._get_sprite_url(),
            img_class=" ".join(classes),
            img_alt=alt or self.pokemon.__repr__(),
            img_height=height,
            img_width=width,
        )

    @abstractmethod
    def _get_sprite_url(self, default: Path = None) -> Path:
        pass

    def _resolve_female_path(self):
        if self.pokemon is None or self.form is None:
            return Path()

        if self.pokemon.species.has_gender_differences and self.form.name.endswith(
            "-female"
        ):
            return Path("female")

        return Path()

    def _resolve_image_path(self):
        is_female_sprite = self._resolve_female_path() == "female"

        if self.pokemon.name != self.form.name and not is_female_sprite:
            suffix = self.form.name.removeprefix(self.pokemon.name)
            return Path(f"{self.pokemon.pokeapi_id}{suffix}.png")

        return Path(f"{self.pokemon.pokeapi_id}.png")

    def _resolve_shiny_path(self) -> Path:
        return Path("shiny" if self.is_shiny_sprite else "")

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


class DefaultSpriteRenderer(PokemonSpriteRenderer):
    def _get_sprite_url(self, default: Path = None) -> Path:
        sprite_url = self.sprites_url

        sprite_url /= self._resolve_shiny_path()
        sprite_url /= self._resolve_female_path()
        sprite_url /= self._resolve_image_path()

        sprite_path = Path(settings.BASE_DIR / sprite_url.relative_to("/"))

        if not sprite_path.exists() or not sprite_path.is_file():
            sprite_resolution_error = "Sprite resolution failed for Pokémon: '%s'"

            if not default:
                raise FileNotFoundError(sprite_resolution_error % self.pokemon)

            default_path = Path(settings.BASE_DIR / default.relative_to("/"))

            if not default_path.exists() or not default_path.is_file():
                raise FileNotFoundError(sprite_resolution_error % self.pokemon)

            return default

        return sprite_url


class HomeSpriteRenderer(DefaultSpriteRenderer):
    @property
    def sprites_url(self) -> Path:
        return super().sprites_url / "other/home"

    def _get_sprite_url(self, default: Path = None) -> Path:
        _default_url = super().sprites_url
        return super()._get_sprite_url(default or _default_url / "0.png")

    def __init__(self, object: SpriteObject, option: SpriteOption = None):
        super().__init__(object, option)
