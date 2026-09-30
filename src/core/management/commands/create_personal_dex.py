from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.management.base import BaseCommand
from home.models import Box, PersonalDex
from home.services import default_forms


class Command(BaseCommand):
    help = _lazy(("Create a personal dex with the default settings."))

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
                _("Working on PersonalDex: `%s`... ") % options["dex_name"]
            ),
            ending="",
        )

        dex, created = PersonalDex.objects.update_or_create(
            name=options["dex_name"],
            defaults={
                "force_new_box": options["force_new_box"],
                "is_shiny_dex": options["shiny_dex"],
            },
        )

        forms = default_forms()

        dex.forms.clear()
        dex.forms.add(*forms)

        self.stdout.write(
            self.style.SUCCESS(_("created!") if created else _("updated!"))
        )

        if options["install_scheme"]:
            if not Box.objects.exists():
                choice = (
                    input(
                        _(
                            "You have to create the Pokémon HOME mirror boxes before "
                            "installing a scheme.\n"
                            "Do you want to do it now? [y/N]: "
                        )
                    )
                    .lower()
                    .strip()
                )

                if choice not in ("y", "yes"):
                    raise CommandError(_("aborted!"))

                call_command(
                    "create_home_boxes", stdout=self.stdout, stderr=self.stderr
                )

            call_command(
                "create_home_scheme",
                personal_dex_id=dex.id,
                first_box_id=Box.objects.first().id,
                clear=True,
                stdout=self.stdout,
                stderr=self.stderr,
            )
