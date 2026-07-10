from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class RegistrationStatusFilter(admin.SimpleListFilter):
    title = _("registration status")
    parameter_name = "is_registred"

    def lookups(self, request, model_admin):
        return (
            (1, _("registred")),
            (0, _("unregistred")),
        )

    def queryset(self, request, queryset):
        if self.value() is not None:
            is_registred = True if int(self.value()) == 1 else False
            return queryset.filter(specimen__isnull=not is_registred)

        return queryset
