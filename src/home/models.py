from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as __
from django.utils.translation import gettext_lazy as _

from core.consts import (
    GENDER_CHOICES,
    LANGUAGES_CHOICES,
    NATURE_CHOICES,
)
from core.models import OrderedModel, TimestampedModel
from home.choices import Pokeball
from pokedex.models import PokemonForm, Version

from .origin_marks import origin_mark_for
from .utils import col_choices, row_choices

DEFAULT_POKEMON_BOX_SIZE = 30


class Box(OrderedModel, TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)

    class Meta:
        verbose_name = _("box")
        verbose_name_plural = _("boxes")

    @property
    def is_empty(self) -> bool:
        return not self.slots.filter(form__isnull=False).exists()

    @property
    def page(self):
        return (self.position - 1) // DEFAULT_POKEMON_BOX_SIZE + 1

    def save(self, *args, **kwargs):
        box = super().save(*args, **kwargs)

        for row in range(5):
            for col in range(6):
                Slot.objects.get_or_create(box=self, row=row, col=col)

        return box

    def __str__(self):
        return self.name


class OriginalTrainer(TimestampedModel):
    name = models.CharField(_("name"), max_length=255)
    trainer_id = models.CharField(_("trainer ID"), max_length=255)
    version = models.ForeignKey(
        Version, on_delete=models.SET_NULL, blank=True, null=True
    )

    class Meta:
        ordering = ("version__version_group__order", "version__name")
        unique_together = ("name", "trainer_id")

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_version_id = instance.version_id
        return instance

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Ganhou ou trocou de versão: leva a nova versão aos espécimes que
        # estavam sem jogo de origem ou com a versão antiga. Um espécime
        # corrigido à mão (outra versão) fica como está.
        old_version_id = getattr(self, "_loaded_version_id", None)
        if self.version_id != old_version_id:
            Specimen.objects.filter(ot=self).filter(
                models.Q(origin_version__isnull=True)
                | models.Q(origin_version_id=old_version_id)
            ).update(origin_version_id=self.version_id)
        self._loaded_version_id = self.version_id

    def __str__(self):
        version_suffix = f" ({self.version})" if self.version else ""
        return f"{self.trainer_id}:{self.name}{version_suffix}"


class PersonalDex(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    forms = models.ManyToManyField(PokemonForm, blank=True)
    is_shiny_dex = models.BooleanField(_("is shiny dex"), default=False)
    force_new_box = models.BooleanField(_("force new Box for each gen"), default=False)

    class Meta:
        verbose_name = _("personal dex")
        verbose_name_plural = _("personal dexes")

    def __str__(self):
        return self.name


class Slot(OrderedModel, TimestampedModel):
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name="slots")
    row = models.IntegerField(_("row"), choices=row_choices)
    col = models.IntegerField(_("col"), choices=col_choices)
    personal_dex = models.ForeignKey(
        PersonalDex,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    form = models.ForeignKey(
        PokemonForm, on_delete=models.SET_NULL, blank=True, null=True
    )
    specimen = models.ForeignKey(
        "Specimen", on_delete=models.SET_NULL, blank=True, null=True
    )

    class Meta:
        verbose_name = _("slot")
        verbose_name_plural = _("slots")
        unique_together = ("box", "row", "col")
        ordering = ("box__position", "position")

    @property
    def is_empty(self):
        return self.specimen is None

    @property
    def is_first(self):
        return self.row == 0 and self.col == 0

    @property
    def is_free(self):
        return self.form is None

    def clean(self):
        super().clean()

        if self.form and self.specimen and self.form != self.specimen.form:
            raise ValidationError(
                {"specimen": _("specimen form doesn't match with slot form.")}
            )

    def __str__(self):
        if self.form:
            specimen = self.specimen if self.specimen else __("no specimen deposited")

            return __("[{box}: {row},{col}] ({form}): {specimen}").format(
                box=self.box,
                form=self.form,
                row=self.row + 1,
                col=self.col + 1,
                specimen=specimen,
            )

        return __("[{box}: {row},{col}] free slot").format(
            box=self.box,
            row=self.row + 1,
            col=self.col + 1,
        )


class Specimen(TimestampedModel):
    form = models.ForeignKey(PokemonForm, on_delete=models.PROTECT)
    form_name = models.CharField(_("form name"), max_length=255, blank=True, null=True)
    nickname = models.CharField(_("nickname"), max_length=255, blank=True, null=True)
    ability = models.CharField(_("ability"), max_length=255, blank=True, null=True)
    language = models.CharField(_("language"), choices=LANGUAGES_CHOICES, default="en")
    gender = models.CharField(_("gender"), choices=GENDER_CHOICES, default="male")
    nature = models.CharField(_("nature"), choices=NATURE_CHOICES, default="hardy")
    is_alpha = models.BooleanField(_("is alpha"), default=False)
    is_shiny = models.BooleanField(_("is shiny"), default=False)
    is_from_go = models.BooleanField(_("is from Pokémon GO"), default=False)
    ot = models.ForeignKey(
        OriginalTrainer, on_delete=models.SET_NULL, blank=True, null=True
    )
    # Jogo de origem (define a marca de origem): derivado do OT no save, ver
    # home.origin_marks. Editável só no admin, para exceções (eventos, trocas).
    origin_version = models.ForeignKey(
        Version,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="origin_specimens",
        verbose_name=_("origin game"),
    )
    captured_at = models.DateField(_("captured at"), blank=True, null=True)
    pokeball = models.CharField(
        _("pokéball"), choices=Pokeball.choices, max_length=255, blank=True, null=True
    )
    observation = models.TextField(_("observation"), blank=True, null=True)

    class Meta:
        verbose_name = _("specimen")
        verbose_name_plural = _("specimens")
        ordering = ("form__order",)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_ot_id = instance.ot_id
        return instance

    def save(self, *args, **kwargs):
        if self.form and not self.form_name:
            self.form_name = self.form.name.strip()

        # Novo espécime ou OT trocado: o jogo de origem passa a ser o do OT
        # (vazio se o OT não tiver versão).
        if self._state.adding or self.ot_id != getattr(self, "_loaded_ot_id", None):
            self.origin_version_id = self.ot.version_id if self.ot else None
            if "update_fields" in kwargs and kwargs["update_fields"] is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "origin_version"}

        super().save(*args, **kwargs)
        self._loaded_ot_id = self.ot_id

    @property
    def origin_mark(self) -> str | None:
        version = self.origin_version
        return origin_mark_for(
            version.version_group.name if version else None, self.is_from_go
        )

    def __str__(self):
        badges = "%(shiny)s%(alpha)s%(pk_go)s%(obsrv)s" % {
            "shiny": "✨" if self.is_shiny else "",
            "alpha": "💢" if self.is_alpha else "",
            "pk_go": "📱" if self.is_from_go else "",
            "obsrv": "❗" if self.observation else "",
        }
        return "{nickname}{badges}".format(
            nickname=f"{self.nickname if self.nickname else self.form_name} ",
            badges=badges,
        )
