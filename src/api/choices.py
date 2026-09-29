"""Labels traduzíveis dos choices de Specimen, expostos em /specimens/options/.

Os choices em core.consts usam o próprio valor como label (e alterá-los
geraria migrações); aqui ficam os labels para o frontend.
"""

from django.utils.translation import gettext_lazy as _

from core.consts import GENDER_CHOICES, LANGUAGES_CHOICES, NATURE_CHOICES
from home.choices import Pokeball

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


def _labeled(choices, labels) -> list[dict]:
    return [
        {"value": value, "label": str(labels.get(value, label))}
        for value, label in choices
    ]


def specimen_options() -> dict[str, list[dict]]:
    return {
        "language": _labeled(LANGUAGES_CHOICES, LANGUAGE_LABELS),
        "gender": _labeled(GENDER_CHOICES, GENDER_LABELS),
        "nature": _labeled(NATURE_CHOICES, NATURE_LABELS),
        "pokeball": _labeled(Pokeball.choices, {}),
    }
