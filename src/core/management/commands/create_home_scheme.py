from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from core.consts import GEN_FIRST_FORM_NAMES
from home.models import Box, PersonalDex, Slot
from pokedex.models import PokemonForm


class Command(BaseCommand):
    help = _lazy(
        "Creates a distribution scheme for `PokemonForm` objects linked to the "
        "`PersonalDex` across Pokémon Home's mirror boxes."
    )

    def __get_boxes(self, f_box: Box, l_box: Box | None = None) -> QuerySet[Box]:
        boxes = Box.objects.filter(position__gte=f_box.position).order_by("position")

        if l_box:
            boxes = boxes.filter(position__lte=l_box.position)

        return boxes.prefetch_related(
            Prefetch("slots", queryset=Slot.objects.order_by("position"))
        )

    def __get_forms(self, p_dex: PersonalDex, capacity: int) -> list[PokemonForm]:
        forms = list(p_dex.forms.all())

        if len(forms) > capacity:
            raise CommandError(
                _(
                    "There isn't enough space in the boxes for all the forms linked to "
                    "this PersonalDex."
                )
            )

        return forms

    def __get_object[T](self, model: type[T], raise_exc: bool, **kwargs) -> T | None:
        try:
            return model.objects.get(**kwargs)
        except model.DoesNotExist as e:
            if raise_exc:
                raise CommandError(e)
            return None

    def __get_object_or_raise[T](self, model: type[T], **kwargs) -> T:
        return self.__get_object(model, raise_exc=True, **kwargs)

    def __get_object_or_none[T](self, model: type[T], **kwargs) -> T | None:
        return self.__get_object(model, raise_exc=False, **kwargs)

    def __install_scheme(self, p_dex: PersonalDex, boxes: QuerySet[Box]):
        slots_by_box = [list(box.slots.all()) for box in boxes]
        total_capacity = sum(len(slots) for slots in slots_by_box)

        forms = self.__get_forms(p_dex, total_capacity)

        if not forms:
            self.stdout.write(self.style.WARNING(_("No forms to install.")))
            return

        index = 0
        total_forms = len(forms)
        slots_to_update = []

        self.stdout.write(
            self.style.MIGRATE_LABEL(_("Installing scheme... ")),
            ending="",
        )

        for slots in slots_by_box:
            for slot in slots:
                if index >= total_forms:
                    break

                current_form = forms[index]
                is_gen_first_form = current_form.name in GEN_FIRST_FORM_NAMES[1:]

                if is_gen_first_form and not slot.is_first and p_dex.force_new_box:
                    break

                slot.form = current_form
                slot.personal_dex = p_dex
                slots_to_update.append(slot)

                index += 1

            if index >= total_forms:
                break

        if slots_to_update:
            Slot.objects.bulk_update(slots_to_update, fields=["form", "personal_dex"])

        self.stdout.write(self.style.SUCCESS(_("done!")))

    def __reset_boxes_scheme(self, boxes: QuerySet[Box], prune=False) -> None:
        self.stdout.write(self.style.WARNING(_("WARNING!")))
        action = _("prune") if prune else _("clear")

        choice = (
            input(
                _(
                    "This action will %(action)s %(boxes_count)d boxes to the default "
                    "configuration. All previous schemes will be lost!"
                    "\n\n!!! THIS CHANGE IS IRREVERSIBLE !!!\n\n"
                    "Do you want to continue? [y/N]: "
                )
                % {
                    "action": action,
                    "boxes_count": boxes.count(),
                }
            )
            .lower()
            .strip()
        )

        if choice in ("y", "yes"):
            self.stdout.write(
                self.style.MIGRATE_LABEL(
                    _("%(action)s previous scheme from %(f_box)s to %(l_box)s... ")
                    % {
                        "action": _("Pruning") if prune else _("Clearing"),
                        "f_box": boxes.first().name,
                        "l_box": boxes.last().name,
                    }
                ),
                ending="",
            )

            update_kwargs = {"form": None, "personal_dex": None}

            if prune:
                update_kwargs["specimen"] = None

            Slot.objects.filter(box__in=boxes).update(**update_kwargs)

            self.stdout.write(self.style.SUCCESS(_("done!")))
        else:
            raise CommandError(_("Operation aborted by user."))

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
                "Note that if the range of boxes didn't have enough space to "
                "accommodate all the forms of the PersonalDex, the command will fail."
            ),
            type=int,
        )
        cleaning_group = parser.add_mutually_exclusive_group(required=False)
        cleaning_group.add_argument(
            "--clear",
            help=_(
                "Clear any existing scheme linked to the affected boxes before "
                "installing the new scheme on them without unlinking the specimen "
                "previously deposited in the slot."
            ),
            action="store_true",
        )
        cleaning_group.add_argument(
            "--prune",
            help=_(
                "Prune any existing scheme linked to the affected boxes before "
                "installing the new scheme on them. This action will also unlink the "
                "specimen previously deposited in the slot."
            ),
            action="store_true",
        )

    @transaction.atomic()
    def handle(self, **options):
        p_dex = self.__get_object_or_raise(PersonalDex, id=options["personal_dex_id"])
        f_box = self.__get_object_or_raise(Box, id=options["first_box_id"])
        l_box = self.__get_object_or_none(Box, id=options["last_box_id"])
        boxes = self.__get_boxes(f_box, l_box)

        if options["clear"] or options["prune"]:
            self.__reset_boxes_scheme(boxes, options["prune"])

        self.__install_scheme(p_dex, boxes)
