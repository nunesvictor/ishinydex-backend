from django.db import models
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
                self.position = 0

        super().save(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ["position"]


class Box(OrderedModel):
    name = models.CharField(_("name"), max_length=255, unique=True)

    def save(self, *args, **kwargs):
        box = super().save(*args, **kwargs)

        for row in range(5):
            for col in range(6):
                BoxSlot.objects.get_or_create(box=self, row=row, col=col)

        return box

    class Meta:
        verbose_name = _("box")
        verbose_name_plural = _("boxes")

    def __str__(self):
        return self.name


class BoxSlot(models.Model):
    box = models.ForeignKey(Box, on_delete=models.CASCADE, related_name="slots")
    row = models.IntegerField(_("row"), choices=row_choices)
    col = models.IntegerField(_("col"), choices=col_choices)
    pokemon = models.CharField(_("pokemon"), max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = _("slot")
        verbose_name_plural = _("slots")
        unique_together = ("box", "row", "col")
        ordering = ["box__position", "row", "col"]

    def __str__(self):
        return f"{self.box.name} - Row: {self.row}, Col: {self.col}"
