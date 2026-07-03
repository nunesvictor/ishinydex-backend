from django.db import models
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from core.models import OrderedModel, TimestampedModel
from pokedex.models import PokemonForm, Version

from .utils import col_choices, row_choices


class Box(OrderedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)

    class Meta:
        verbose_name = _("box")
        verbose_name_plural = _("boxes")

    @property
    def page(self):
        return (self.position - 1) // 30 + 1

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
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    class Meta:
        ordering = ("version__version_group__order", "version__name")

    def __str__(self):
        return f"{self.trainer_id} {self.name} ({self.version})"


class PersonalDex(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    forms = models.ManyToManyField(PokemonForm, blank=True)
    is_shiny_dex = models.BooleanField(_("is shiny dex"), default=False)

    class Meta:
        verbose_name = _("personal dex")
        verbose_name_plural = _("personal dex")

    def __str__(self):
        return self.name


class Slot(OrderedModel):
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
        ordering = ["box__position", "row", "col"]

    def __str__(self):
        return gettext(
            "[{box}: {row},{col}] ({form}): {specimen}".format(
                box=self.box,
                row=self.row + 1,
                col=self.col + 1,
                form=self.form if self.form else gettext("no form defined"),
                specimen=self.specimen if self.specimen else gettext("empty slot"),
            )
        )


class Specimen(TimestampedModel):
    form = models.ForeignKey(PokemonForm, on_delete=models.CASCADE)
    nickname = models.CharField(_("nickname"), max_length=255, blank=True, null=True)
    ability = models.CharField(_("ability"), max_length=255, blank=True, null=True)
    language = models.CharField(_("language"), max_length=255, default="en")
    gender = models.CharField(_("gender"), max_length=255, default="genderless")
    nature = models.CharField(_("nature"), max_length=255, default="hardy")
    is_alpha = models.BooleanField(_("is alpha"), default=False)
    is_shiny = models.BooleanField(_("is shiny"), default=False)
    ot = models.ForeignKey(
        OriginalTrainer, on_delete=models.SET_NULL, blank=True, null=True
    )
    captured_at = models.DateField(_("captured at"), blank=True, null=True)

    class Meta:
        verbose_name = _("specimen")
        verbose_name_plural = _("specimens")
        ordering = ("form__order",)

    def __str__(self):
        return "{shiny_icon}{alpha_icon}{nickname}{ot_suffix}".format(
            shiny_icon="✨" if self.is_shiny else "",
            alpha_icon="💢" if self.is_alpha else "",
            nickname=f" {self.nickname if self.nickname else self.form.name}",
            ot_suffix=f" (OT: {self.ot.trainer_id})" if self.ot else "",
        )
