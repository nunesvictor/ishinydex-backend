from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from core.consts import GEN_FIRST_FORM_NAMES
from home.models import Box, PersonalDex
from pokedex.models import PokemonForm


class Command(BaseCommand):
    help = _(
        (
            "Creates a distribution scheme for `PokemonForm` objects linked to the "
            "`PersonalDex` across Pokémon Home's mirror boxes."
        )
    )

    def __get_boxes(self, f_box: Box, l_box: Box | None = None) -> QuerySet[Box]:
        boxes = Box.objects.filter(position__gte=f_box.position)

        if l_box:
            boxes = boxes.filter(position__lte=l_box.position)

        return boxes

    def __get_forms(
        self, p_dex: PersonalDex, boxes: QuerySet[Box]
    ) -> QuerySet[PokemonForm]:
        forms = p_dex.forms.all()

        if forms.count() > sum([b.slots.count() for b in boxes]):
            raise CommandError(
                _(
                    "There isn't enough space in the boxes for all the forms linked to "
                    "this PersonalDex."
                )
            )

        return forms

    def __get_object[T](
        self, model: type[T], raise_exc: bool, *args, **kwargs
    ) -> T | None:
        try:
            return model.objects.get(*args, **kwargs)
        except model.DoesNotExist as e:
            if raise_exc:
                raise CommandError(e)

            return None

    def __get_object_or_raise[T](self, model: type[T], *args, **kwargs) -> T:
        return self.__get_object(model, raise_exc=True, *args, **kwargs)

    def __get_object_or_none[T](self, model: type[T], *args, **kwargs) -> T | None:
        return self.__get_object(model, raise_exc=False, *args, **kwargs)

    def __install_scheme(self, p_dex: PersonalDex, boxes: QuerySet[Box]):
        forms = self.__get_forms(p_dex, boxes)
        index = 0

        self.stdout.write(
            self.style.MIGRATE_LABEL(_("Installing scheme... ")),
            ending="",
        )

        for box in boxes:
            for slot in box.slots.all():
                try:
                    is_gen_first_form = forms[index].name in GEN_FIRST_FORM_NAMES[1:]

                    if is_gen_first_form and not slot.is_first and p_dex.force_new_box:
                        # break the loop to start at a new box
                        break

                    slot.form = forms[index]
                    slot.personal_dex = p_dex

                    slot.save()
                except IndexError:
                    self.stdout.write(self.style.SUCCESS(_("done!")))
                    return

                index += 1

    def __restore_default_scheme(self, boxes: QuerySet[Box]) -> None:
        self.stdout.write(self.style.WARNING(_("WARNING!")))

        choice = (
            input(
                _(
                    "This action will reset %d boxes to the default configuration. "
                    "All previous schemes will be lost!\nTHIS CHANGE IS IRREVERSIBLE. "
                    "Do you want to continue? [y/N]: " % boxes.count()
                )
            )
            .lower()
            .strip()
        )

        if choice in ("y", "yes"):
            self.stdout.write(
                self.style.MIGRATE_LABEL(_("Clearing previus scheme... ")),
                ending="",
            )

            for box in boxes:
                for slot in box.slots.all():
                    slot.form = None
                    slot.specimen = None
                    slot.personal_dex = None

                    slot.save()

            self.stdout.write(self.style.SUCCESS(_("done!")))
        else:
            self.stdout.write(self.style.ERROR(_("aborted!")))

    def add_arguments(self, parser):
        parser.add_argument(
            "-p",
            "--personal-dex-id",
            help=_(
                "The instance ID of the PersonalDex containing the forms to be "
                "organized by the scheme."
            ),
            required=True,
            type=int,
        )
        parser.add_argument(
            "-f",
            "--first-box-id",
            help=_(
                "The ID of the first Box to be used by the schema. The schema will "
                "use as many boxes as necessary to accommodate all PokemonForms from "
                "the PersonalDex, following the box order defined by the `position` "
                "attribute."
            ),
            required=True,
            type=int,
        )
        parser.add_argument(
            "-l",
            "--last-box-id",
            help=_(
                "The ID of the last box that the scheme is allowed to use. Use only "
                "if you have multiples PersonalDexes using different ranges of boxes. "
                "Note that if the range of boxes did't have enough space to acommodate "
                "all the forms of the PersonalDex, the command will fail."
            ),
            type=int,
        )
        parser.add_argument(
            "-o",
            "--override",
            help=_("Clear all previous schemes before creating the new one."),
            action="store_true",
        )

    @transaction.atomic()
    def handle(self, *args, **options):
        p_dex = self.__get_object_or_raise(PersonalDex, id=options["personal_dex_id"])
        f_box = self.__get_object_or_raise(Box, id=options["first_box_id"])
        l_box = self.__get_object_or_none(Box, id=options["last_box_id"])
        boxes = self.__get_boxes(f_box, l_box)

        if options["override"]:
            self.__restore_default_scheme(boxes)

        self.__install_scheme(p_dex, boxes)
