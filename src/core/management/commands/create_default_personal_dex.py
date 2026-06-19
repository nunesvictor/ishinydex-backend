from functools import reduce
from operator import or_

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.translation import gettext as _

from home.models import PersonalDex
from pokedex.models import PokemonForm

_DEFAULT_FORM_ONLY_LIST = [
    "arceus",
    "calyrex",
    "genesect",
    "koraidon",
    "miraidon",
    "mothim",
    "pichu",
    "scatterbug",
    "silvally",
    "spewpa",
]

_DEFAULT_KWARGS_LOOKUPS = (
    {"name__icontains": "-totem"},
    {"name__iendswith": "-origin"},
    {"name__iendswith": "-power-construct"},
    {"name__iendswith": "-starter"},
    {"name__iexact": "eternatus-eternamax"},
    {"name__iexact": "minior-red-meteor"},
    {"name__istartswith": "calyrex-"},
    {"name__istartswith": "kyurem-"},
    {"name__istartswith": "necrozma-"},
    {"name__istartswith": "ogerpon-"},
    {"name__istartswith": "pikachu-"},
)

_DEFAULT_EXTRA_ARGS = (
    Q(pokemon__name="alcremie") & ~Q(name__istartswith="alcremie-vanilla"),
)


class Command(BaseCommand):
    help = _(
        (
            "Create mirror boxes for Pokémon Home. This will create 30 boxes with 30 "
            "slots each, mirroring the structure of Pokémon Home."
        )
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "dex_name",
            type=str,
            help=_("personal dex name"),
            default=_("new personal dex"),
            nargs="?",
        )

    def handle(self, *args, **options):
        dex = PersonalDex.objects.get_or_create(name=options["dex_name"])[0]
        forms = (
            PokemonForm.objects.filter(is_battle_only=False)
            .exclude(
                Q(pokemon__species__name__in=_DEFAULT_FORM_ONLY_LIST)
                & Q(is_default=False)
            )
            .exclude(
                reduce(or_, (Q(**lookup) for lookup in _DEFAULT_KWARGS_LOOKUPS), Q())
            )
            .exclude(*_DEFAULT_EXTRA_ARGS)
        )

        dex.forms.clear()
        dex.forms.add(*forms)

        self.stdout.write(
            self.style.SUCCESS(_("successfully created personal dex: %s" % dex.name))
        )
