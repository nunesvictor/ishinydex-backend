from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from home.models import Box


class Command(BaseCommand):
    help = _lazy(
        (
            "Create mirror boxes for Pokémon Home. This will create the number of "
            "boxes passed in the `box_count` argument (default: 200) with 30 slots "
            "each, mirroring the structure of Pokémon Home."
        )
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "box_count",
            type=int,
            help=_("Number of boxes to create (default: 200)"),
            nargs="?",
            default=200,
        )

    @transaction.atomic()
    def handle(self, *args, **options):
        box_count = options["box_count"]

        self.stdout.write(
            self.style.MIGRATE_LABEL(_("Creating Pokémon HOME Mirror Boxes... ")),
            ending="",
        )

        try:
            for b_index in range(1, box_count + 1):
                Box.objects.create(name=f"HOME {b_index}")
        except BaseException:
            self.stdout.write(self.style.ERROR(_("failure!")))
            raise CommandError(_("Error creating Pokémon Home boxes mirror"))

        self.stdout.write(self.style.SUCCESS(_("success!")))
