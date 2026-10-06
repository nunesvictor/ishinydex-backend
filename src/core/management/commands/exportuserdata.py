import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.management.base import BaseCommand
from home.userdata import build_user_data


class Command(BaseCommand):
    help = _lazy(
        "Export the user's data (trainers, saves, dexes, boxes, shiny locks, "
        "specimens and slots) as a data file that the local app can import."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            help=_(
                "Output file (default: ishinydex-YYYY-MM-DD.json in the backups "
                "folder)."
            ),
        )
        parser.add_argument(
            "--catalog-version",
            dest="catalog_version",
            default="",
            help=_("Catalog version recorded in the file (optional)."),
        )

    def handle(self, *args, **options):
        data = build_user_data(options["catalog_version"])
        output = options["output"]
        file = (
            Path(output)
            if output
            else Path(settings.BACKUPS_DIR) / f"ishinydex-{date.today()}.json"
        )
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        counts = ", ".join(
            f"{key}={len(records)}" for key, records in data["records"].items()
        )
        deposited = sum(1 for s in data["records"]["slots"] if s["specimen"])
        self.stdout.write(
            self.style.SUCCESS(
                _("%(file)s written (%(size)d KB): %(counts)s, deposited=%(deposited)d")
                % {
                    "file": file,
                    "size": file.stat().st_size // 1024,
                    "counts": counts,
                    "deposited": deposited,
                }
            )
        )
