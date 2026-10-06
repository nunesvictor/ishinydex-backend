"""Labels traduzíveis dos choices de Specimen, que vão para o catálogo do app
(``options``).

Os choices em core.consts usam o próprio valor como label (e alterá-los
geraria migrações); aqui ficam os labels para o frontend.
"""

from django.utils.translation import gettext_lazy as _

from core.consts import GENDER_CHOICES, LANGUAGES_CHOICES, NATURE_CHOICES
from home.choices import Pokeball
from home.origin_marks import origin_mark_options

LANGUAGE_LABELS = {
    "ja-hrkt": _("Japanese (kana)"),
    "ja-roma": _("Japanese (romaji)"),
    "ko": _("Korean"),
    "zh-hant": _("Chinese (traditional)"),
    "fr": _("French"),
    "de": _("German"),
    "es": _("Spanish (Spain)"),
    "it": _("Italian"),
    "en": _("English"),
    "cs": _("Czech"),
    "ja": _("Japanese"),
    "zh-hans": _("Chinese (simplified)"),
    "pt-br": _("Brazilian Portuguese"),
    "es-419": _("Spanish (Latin America)"),
}

GENDER_LABELS = {
    "male": _("Male"),
    "female": _("Female"),
    "genderless": _("Genderless"),
}

NATURE_LABELS = {
    "adamant": _("Adamant"),
    "bashful": _("Bashful"),
    "bold": _("Bold"),
    "brave": _("Brave"),
    "calm": _("Calm"),
    "careful": _("Careful"),
    "docile": _("Docile"),
    "gentle": _("Gentle"),
    "hardy": _("Hardy"),
    "hasty": _("Hasty"),
    "impish": _("Impish"),
    "jolly": _("Jolly"),
    "lax": _("Lax"),
    "lonely": _("Lonely"),
    "mild": _("Mild"),
    "modest": _("Modest"),
    "naive": _("Naive"),
    "naughty": _("Naughty"),
    "quiet": _("Quiet"),
    "quirky": _("Quirky"),
    "rash": _("Rash"),
    "relaxed": _("Relaxed"),
    "sassy": _("Sassy"),
    "serious": _("Serious"),
    "timid": _("Timid"),
}

# Stat que cada natureza aumenta e diminui (10%); as neutras não mexem em
# nenhum. Os nomes são os de ``stats`` da forma (PokéAPI).
NATURE_STATS = {
    "lonely": ("attack", "defense"),
    "brave": ("attack", "speed"),
    "adamant": ("attack", "special-attack"),
    "naughty": ("attack", "special-defense"),
    "bold": ("defense", "attack"),
    "relaxed": ("defense", "speed"),
    "impish": ("defense", "special-attack"),
    "lax": ("defense", "special-defense"),
    "timid": ("speed", "attack"),
    "hasty": ("speed", "defense"),
    "jolly": ("speed", "special-attack"),
    "naive": ("speed", "special-defense"),
    "modest": ("special-attack", "attack"),
    "mild": ("special-attack", "defense"),
    "quiet": ("special-attack", "speed"),
    "rash": ("special-attack", "special-defense"),
    "calm": ("special-defense", "attack"),
    "gentle": ("special-defense", "defense"),
    "sassy": ("special-defense", "speed"),
    "careful": ("special-defense", "special-attack"),
}


# Tipos que as formas podem ter (sem "stellar", "unknown" e "shadow").
TYPE_LABELS = {
    "normal": _("Normal"),
    "fire": _("Fire"),
    "water": _("Water"),
    "grass": _("Grass"),
    "electric": _("Electric"),
    "ice": _("Ice"),
    "fighting": _("Fighting"),
    "poison": _("Poison"),
    "ground": _("Ground"),
    "flying": _("Flying"),
    "psychic": _("Psychic"),
    "bug": _("Bug"),
    "rock": _("Rock"),
    "ghost": _("Ghost"),
    "dragon": _("Dragon"),
    "dark": _("Dark"),
    "steel": _("Steel"),
    "fairy": _("Fairy"),
}

# Valores de PokemonSpecies.generation (PokéAPI), em ordem.
GENERATIONS = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix")


def _labeled(choices, labels) -> list[dict]:
    return [
        {"value": value, "label": str(labels.get(value, label))}
        for value, label in choices
    ]


def nature_options() -> list[dict]:
    """Naturezas com o stat aumentado e o diminuído (``None`` nas neutras)."""
    return [
        option
        | dict(
            zip(
                ("increased", "decreased"),
                NATURE_STATS.get(option["value"], (None, None)),
            )
        )
        for option in _labeled(NATURE_CHOICES, NATURE_LABELS)
    ]


def specimen_options() -> dict[str, list[dict]]:
    return {
        "language": _labeled(LANGUAGES_CHOICES, LANGUAGE_LABELS),
        "gender": _labeled(GENDER_CHOICES, GENDER_LABELS),
        "nature": nature_options(),
        "pokeball": _labeled(Pokeball.choices, {}),
        "type": [
            {"value": value, "label": str(label)}
            for value, label in TYPE_LABELS.items()
        ],
        "generation": [
            {
                "value": f"generation-{roman}",
                "label": _("Generation %(number)s") % {"number": roman.upper()},
            }
            for roman in GENERATIONS
        ],
        "origin_mark": origin_mark_options(),
    }
