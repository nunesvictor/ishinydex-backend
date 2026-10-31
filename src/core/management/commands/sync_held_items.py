import time

from django.core.management.base import CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.management.base import BaseCommand
from core.services.pokeapi import PokeAPIClient
from pokedex.held_items import HeldItemsError, HeldItemsImporter
from pokedex.showdown import ShowdownError, ShowdownItems


class Command(BaseCommand):
    help = _lazy(
        "Import the held items of each version group from a Pokémon Showdown "
        "clone (data/items.ts and data/mods), matched with the PokéAPI items. "
        "Run after sync_pokeapi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "showdown",
            help=_("Path to a clone of smogon/pokemon-showdown (with data/)."),
        )

    def get_client(self) -> PokeAPIClient:
        return PokeAPIClient()

    def handle(self, *args, **options):
        started = time.perf_counter()
        try:
            importer = HeldItemsImporter(
                self.get_client(),
                ShowdownItems(options["showdown"]),
                log=self.stdout.write,
            )
            count = importer.run()
        except (HeldItemsError, ShowdownError) as error:
            raise CommandError(str(error))
        self.stdout.write(
            self.style.SUCCESS(
                _("Done in %(seconds).1fs: held_items=%(count)d")
                % {"seconds": time.perf_counter() - started, "count": count}
            )
        )
