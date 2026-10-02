from django.db import models
from django.db.models.base import ModelBase
from django.utils.translation import gettext_lazy as _


class FinalFieldsMetaclass(ModelBase):
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        end_of_table_fields = ("position", "created_at", "updated_at")

        if new_class._meta.abstract:
            return new_class

        fields = new_class._meta.local_fields

        for field_name in end_of_table_fields:
            field = next((f for f in fields if f.name == field_name), None)

            if field:
                fields.remove(field)
                fields.append(field)

        return new_class


class OrderedModel(models.Model, metaclass=FinalFieldsMetaclass):
    # Criado pelo Django em cada modelo concreto; anotado para o pyright.
    id: int
    position = models.PositiveIntegerField(_("position"), editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            last_item = type(self).objects.order_by("position").last()

            if last_item:
                self.position = last_item.position + 1
            else:
                self.position = 1

        super().save(*args, **kwargs)

    class Meta:
        abstract = True
        ordering = ["position"]


class TimestampedModel(models.Model, metaclass=FinalFieldsMetaclass):
    id: int
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
