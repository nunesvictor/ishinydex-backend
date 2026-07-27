from functools import reduce
from operator import or_

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from home.models import Box, PersonalDex
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
    {"name__iexact": "greninja-battle-bond"},
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
    help = _(("Create a personal dex with the default settings."))

    def add_arguments(self, parser):
        parser.add_argument(
            "dex_name",
            type=str,
            help=_("PersonalDex name"),
            default=_("New PersonalDex"),
            nargs="?",
        )
        parser.add_argument("-f", "--force-new-box", action="store_true")
        parser.add_argument("-i", "--install-scheme", action="store_true")
        parser.add_argument("-s", "--shiny-dex", action="store_true")

    @transaction.atomic()
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.MIGRATE_LABEL(
                _("Working on PersonalDex: `%s`... " % options["dex_name"])
            ),
            ending="",
        )

        dex, created = PersonalDex.objects.update_or_create(
            name__iexact=options["dex_name"],
            defaults={
                "force_new_box": options["force_new_box"],
                "is_shiny_dex": options["shiny_dex"],
            },
        )

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
            self.style.SUCCESS(_("%s" % "created!" if created else "updated!"))
        )

        if options["install_scheme"]:
            call_command(
                "create_home_scheme",
                personal_dex_id=dex.id,
                first_box_id=Box.objects.first().id,
                clear=True,
            )
