import logging
from abc import ABCMeta, abstractmethod
from pathlib import Path

from django.utils.translation import gettext_lazy as _

from core.consts import HOME_SPRITE_BASE_PATH
from core.typing import SpriteObject, SpriteOption
from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

logger = logging.getLogger(__name__)


class SpritePathResolver(metaclass=ABCMeta):
    @abstractmethod
    def resolve_path(self) -> Path:
        pass

    @property
    def is_pokemon(self):
        return isinstance(self.object, Pokemon)

    @property
    def is_pokemonform(self):
        return isinstance(self.object, PokemonForm)

    @property
    def is_slot(self):
        return isinstance(self.object, Slot)

    @property
    def is_shiny(self):
        if self.option == "shiny":
            return True

        if not self.option and self.is_slot:
            p_dex = self.object.personal_dex or None
            return p_dex and p_dex.is_shiny_dex

        return False

    def _get_pokemon_and_form(self) -> tuple[Pokemon | None, PokemonForm | None]:
        if self.is_slot:
            if not hasattr(self.object, "form") or self.object.form is None:
                logger.warning(
                    _(
                        "%s doesn't have a PokemonForm instance associate with it."
                        % type(self.object)
                    )
                )
                return None, None

            return self._get_pokemon_and_form(self.object.form)

        if self.is_pokemonform:
            if not hasattr(self.object, "pokemon") or self.object.form is None:
                logger.warning(
                    _(
                        "%s doesn't have a Pokemon instance associate with it."
                        % type(self.object)
                    )
                )
                return None, None

            return self.object.pokemon, self.object

        if self.is_pokemon:
            form = self.object.forms.filter(is_default=True).first()

            if not form:
                logger.warning(
                    _("Couldn't find a default form for Pokemon: %s" % self.object)
                )
                return None, None

            return (self.objectobj, form)

        raise ValueError(_("Could't retrive a form from %s object" % type(obj)))

    def __init__(self, object: SpriteObject, option: SpriteOption = None):
        self.object = object
        self.option = option


class HomeSpritePathResolver(SpritePathResolver):
    def _resolve_shiny_path_slice(self) -> Path:
        return Path("shiny" if self.is_shiny else "")

    def _resolve_female_path_slice(self):
        pass

    def resolve_path(self) -> Path:
        path = HOME_SPRITE_BASE_PATH
        path /= self._resolve_shiny_path_slice()
        path /= self._resolve_female_path_slice()
