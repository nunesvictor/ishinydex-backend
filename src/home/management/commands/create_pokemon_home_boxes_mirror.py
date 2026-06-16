from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from ...models import Box


class Command(BaseCommand):
    help = _(
        (
            "Create mirror boxes for Pokémon Home. This will create 30 boxes with 30 "
            "slots each, mirroring the structure of Pokémon Home."
        )
    )

    def add_arguments(self, parser):
        # Optional: Add positional or optional arguments (flags)
        parser.add_argument(
            "box_count",
            type=int,
            help=_("Number of boxes to create (default: 200)"),
            nargs="?",
            default=200,
        )

    def handle(self, *args, **options):
        box_count = options["box_count"]

        for b_index in range(1, box_count + 1):
            Box.objects.get_or_create(name=f"HOME {b_index}")

        self.stdout.write(
            self.style.SUCCESS(_("Successfully created mirror boxes for Pokémon Home."))
        )
