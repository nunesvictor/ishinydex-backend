import json
from datetime import date
from pathlib import Path

from django.core.management.base import CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from api.catalog import CatalogError, build_catalog
from core.management.base import BaseCommand


class Command(BaseCommand):
    help = _lazy(
        "Export the reference data (forms, pokémon, species, versions, choices "
        "and default shiny locks) as the catalog package used by the app."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="catalog",
            help=_("Output directory (default: catalog)."),
        )
        parser.add_argument(
            "--catalog-version",
            dest="catalog_version",
            default=f"catalog-{date.today():%Y.%m.%d}",
            help=_("Catalog version (default: catalog-YYYY.MM.DD of today)."),
        )

    def handle(self, *args, **options):
        try:
            catalog = build_catalog(options["catalog_version"])
        except CatalogError as error:
            raise CommandError(str(error))
        output = Path(options["output"])
        output.mkdir(parents=True, exist_ok=True)
        file = output / "catalog.json"
        file.write_text(
            json.dumps(catalog, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        counts = ", ".join(
            f"{key}={len(catalog[key])}"
            for key in ("forms", "pokemon", "species", "versions", "defaultDex")
        )
        self.stdout.write(
            self.style.SUCCESS(
                _("%(version)s written to %(file)s (%(size)d KB): %(counts)s")
                % {
                    "version": catalog["version"],
                    "file": file,
                    "size": file.stat().st_size // 1024,
                    "counts": counts,
                }
            )
        )
