from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class RegistrationStatusFilter(admin.SimpleListFilter):
    title = _("registration status")
    parameter_name = "is_registered"

    def lookups(self, request, model_admin):
        return (
            (1, _("registred")),
            (0, _("unregistred")),
        )

    def queryset(self, request, queryset):
        match self.value():
            case "1":
                return queryset.filter(specimen__isnull=False)
            case "0":
                return queryset.filter(specimen__isnull=True)

        return queryset
