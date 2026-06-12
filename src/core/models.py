from django.db import models
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from .utils import col_choices, row_choices


class OrderedModel(models.Model):
    position = models.PositiveIntegerField(_("position"), editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            last_item = self._meta.model.objects.all().order_by("position").last()

            if last_item:
                self.position = last_item.position + 1
            else:
                self.position = 1

        super().save(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ["position"]


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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


class PokemonSpecimen(TimestampedModel):
    ndex_id = models.PositiveIntegerField(_("national dex number"), unique=True)
    species = models.CharField(_("species"), max_length=255)
    nickname = models.CharField(_("nickname"), max_length=255, blank=True, null=True)
    language = models.CharField(_("language"), max_length=255, default="en")
    gender = models.CharField(_("gender"), max_length=255, default="genderless")
    form = models.CharField(_("form"), max_length=255, blank=True, null=True)
    is_gmax = models.BooleanField(_("is gmax"), default=False)
    is_legendary = models.BooleanField(_("is legendary"), default=False)
    is_mega = models.BooleanField(_("is mega"), default=False)
    is_mythical = models.BooleanField(_("is mythical"), default=False)
    is_shiny = models.BooleanField(_("is shiny"), default=False)
    ot_name = models.CharField(_("original trainer name"), max_length=255)
    ot_id = models.CharField(_("original trainer ID"), max_length=255)
    og_generation = models.CharField(_("game generation"), max_length=255)
    og_version_group = models.CharField(_("game version group"), max_length=255)
    og_version_name = models.CharField(_("game version name"), max_length=255)
    captured_at = models.DateField(_("captured at"))

    class Meta:
        verbose_name = _("pokémon specimen")
        verbose_name_plural = _("pokémon specimens")

    def save(self, *args, **kwargs):
        self.form = self.species if self.form is None else self.form
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            self.nickname if self.nickname else f"#{self.ndex_id:04d}: {self.species}"
        )


class Slot(OrderedModel):
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name="slots")
    row = models.IntegerField(_("row"), choices=row_choices)
    col = models.IntegerField(_("col"), choices=col_choices)
    specimen = models.ForeignKey(
        PokemonSpecimen, on_delete=models.SET_NULL, blank=True, null=True
    )

    class Meta:
        verbose_name = _("slot")
        verbose_name_plural = _("slots")
        unique_together = ("box", "row", "col")
        ordering = ["box__position", "row", "col"]

    def __str__(self):
        return str(self.specimen) if self.specimen else gettext("Empty Slot")
