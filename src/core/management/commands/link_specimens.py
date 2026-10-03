from django.core.management.base import CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.management.base import BaseCommand
from home.models import PersonalDex
from home.services import link_specimens


class Command(BaseCommand):
    help = _lazy(
        "Deposit existing specimens into the empty slots of a PersonalDex scheme. "
        "Prefers specimens matching the dex shininess and never reuses a specimen "
        "already deposited in a slot."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "dex",
            nargs="*",
            help=_("PersonalDex names or IDs (default: all)."),
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help=_(
                "Only deposit specimens matching the dex shininess (shiny specimens "
                "for shiny dexes and vice-versa)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=_("Show what would be linked without saving."),
        )

    def _get_dexes(self, identifiers: list[str]) -> list[PersonalDex]:
        if not identifiers:
            return list(PersonalDex.objects.order_by("id"))

        dexes = []

        for identifier in identifiers:
            lookup = (
                {"pk": identifier} if identifier.isdigit() else {"name": identifier}
            )

            try:
                dexes.append(PersonalDex.objects.get(**lookup))
            except PersonalDex.DoesNotExist:
                raise CommandError(_("PersonalDex not found: %s") % identifier)

        return dexes

    def handle(self, *args, **options):
        linked, missing = link_specimens(
            self._get_dexes(options["dex"]),
            strict=options["strict"],
            dry_run=options["dry_run"],
        )

        for slot in linked:
            self.stdout.write(
                f"  [{slot.box}: {slot.row + 1},{slot.col + 1}] "
                f"{slot.form.name} <- {slot.specimen}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                _("%(linked)d slots linked, %(missing)d without a free specimen.")
                % {"linked": len(linked), "missing": missing}
            )
        )
