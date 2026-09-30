from collections import defaultdict

from django.core.management.base import CommandError
from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.management.base import BaseCommand
from home.models import PersonalDex, Slot, Specimen


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

    @transaction.atomic
    def handle(self, *args, **options):
        slots = list(
            Slot.objects.filter(
                personal_dex__in=self._get_dexes(options["dex"]),
                form__isnull=False,
                specimen__isnull=True,
            )
            .select_related("personal_dex", "box", "form")
            .order_by("box__position", "position")
        )

        # Espécimes livres (fora de qualquer slot), agrupados por forma e brilho.
        free = defaultdict(list)
        for specimen in (
            Specimen.objects.filter(
                form_id__in={s.form_id for s in slots}, slot__isnull=True
            )
            .order_by("id")
            .iterator()
        ):
            free[(specimen.form_id, specimen.is_shiny)].append(specimen)

        linked, missing = [], []

        for slot in slots:
            wanted = slot.personal_dex.is_shiny_dex
            candidates = [(slot.form_id, wanted)]

            if not options["strict"]:
                candidates.append((slot.form_id, not wanted))

            pool = next((free[key] for key in candidates if free[key]), None)

            if pool is None:
                missing.append(slot)
                continue

            slot.specimen = pool.pop(0)
            linked.append(slot)
            self.stdout.write(
                f"  [{slot.box}: {slot.row + 1},{slot.col + 1}] "
                f"{slot.form.name} <- {slot.specimen}"
            )

        if options["dry_run"]:
            transaction.set_rollback(True)
        else:
            Slot.objects.bulk_update(linked, ["specimen"])

        self.stdout.write(
            self.style.SUCCESS(
                _("%(linked)d slots linked, %(missing)d without a free specimen.")
                % {"linked": len(linked), "missing": len(missing)}
            )
        )
