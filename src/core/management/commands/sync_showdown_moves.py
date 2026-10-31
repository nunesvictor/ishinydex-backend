import time

from django.core.management.base import CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.management.base import BaseCommand
from pokedex.showdown_moves import ShowdownMovesError, ShowdownMovesImporter


class Command(BaseCommand):
    help = _lazy(
        "Import the moves of the games the PokéAPI lacks (Legends: Z-A) from a "
        "Pokémon Showdown clone (data/mods/*/learnsets.ts). Run after "
        "sync_pokeapi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "showdown",
            help=_("Path to a clone of smogon/pokemon-showdown (with data/)."),
        )

    def handle(self, *args, **options):
        started = time.perf_counter()
        try:
            count = ShowdownMovesImporter(
                options["showdown"], log=self.stdout.write
            ).run()
        except ShowdownMovesError as error:
            raise CommandError(str(error))
        self.stdout.write(
            self.style.SUCCESS(
                _("Done in %(seconds).1fs: move_learns=%(count)d")
                % {"seconds": time.perf_counter() - started, "count": count}
            )
        )
