from django.db import models
from django.utils.translation import gettext_lazy as _


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
