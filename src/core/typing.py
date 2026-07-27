from typing import Literal

from home.models import Slot
from pokedex.models import Pokemon, PokemonForm

type SpriteObject = Pokemon | PokemonForm | Slot
type SpriteOption = Literal["default", "shiny"] | None
