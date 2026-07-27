from pathlib import Path

from django.conf import settings

GEN_FIRST_FORM_NAMES = (
    "bulbasaur",
    "chikorita",
    "treecko",
    "turtwig",
    "victini",
    "chespin",
    "rowlet",
    "grookey",
    "sprigatito",
)

HOME_SPRITE_BASE_PATH = Path(settings.MEDIA_ROOT / "sprites/pokemon/other/home/")
