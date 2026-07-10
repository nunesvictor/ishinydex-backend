from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from core.models import OrderedModel, TimestampedModel
from pokedex.models import PokemonForm, Version

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

    def __str__(self):
        version_suffix = f" ({self.version})" if self.version else ""
        return f"{self.trainer_id} {self.name}{version_suffix}"


class PersonalDex(TimestampedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)
    forms = models.ManyToManyField(PokemonForm, blank=True)
    is_shiny_dex = models.BooleanField(_("is shiny dex"), default=False)
    force_new_box = models.BooleanField(_("force new Box for each gen"), default=False)

    class Meta:
        verbose_name = _("PersonalDex")
        verbose_name_plural = _("PersonalDexes")

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
    is_from_go = models.BooleanField(_("is from Pokémon GO"), default=False)
    ot = models.ForeignKey(
        OriginalTrainer, on_delete=models.SET_NULL, blank=True, null=True
    )
    captured_at = models.DateField(_("captured at"), blank=True, null=True)

    class Meta:
        verbose_name = _("specimen")
        verbose_name_plural = _("specimens")
        ordering = ("form__order",)

    def __str__(self):
        return "{nickname}{shiny_icon}{alpha_icon}{ot_suffix}{go_suffix}".format(
            shiny_icon="✨" if self.is_shiny else "",
            alpha_icon="💢" if self.is_alpha else "",
            go_suffix="📱" if self.is_from_go else "",
            nickname=f" {self.nickname if self.nickname else self.form.name}",
            ot_suffix=f" (OT: {self.ot.trainer_id})" if self.ot else "",
        )
