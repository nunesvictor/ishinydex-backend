import time

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.services.pokeapi import PokeAPIClient
from pokedex.importer import PokeAPIImporter, UnknownSpeciesError


class Command(BaseCommand):
    help = _lazy(
        "Import/update species, pokémon, forms and versions from PokéAPI. "
        "Responses are cached on disk, so later runs work offline."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "species",
            nargs="*",
            help=_lazy(
                "Species names to import (default: all). Their pokémon, forms "
                "and versions are imported too."
            ),
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help=_lazy("Download everything again, ignoring the local cache."),
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=8,
            help=_lazy("Number of parallel downloads (default: 8)."),
        )

    def get_client(self, **options) -> PokeAPIClient:
        return PokeAPIClient(refresh=options["refresh"], max_workers=options["workers"])

    def handle(self, *args, **options):
        started = time.perf_counter()
        importer = PokeAPIImporter(self.get_client(**options), log=self.stdout.write)

        try:
            counts = importer.run(options["species"] or None)
        except UnknownSpeciesError as error:
            raise CommandError(_("Unknown species: %s") % error)

        summary = ", ".join(f"{name}={count}" for name, count in counts.items())
        self.stdout.write(
            self.style.SUCCESS(
                _("Done in %(seconds).1fs: %(summary)s")
                % {"seconds": time.perf_counter() - started, "summary": summary}
            )
        )
