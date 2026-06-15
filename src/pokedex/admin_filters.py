from django.contrib import admin
from django.utils.translation import gettext as _


class EggGroupFilter(admin.SimpleListFilter):
    title = _("egg group")
    parameter_name = "egg_group"

    def lookups(self, request, model_admin):
        queryset = model_admin.get_queryset(request)
        egg_groups = set()

        for item in queryset.values_list("egg_groups", flat=True):
            if isinstance(item, list):
                egg_groups.update(item)

        return sorted([(eg, eg.title()) for eg in egg_groups if eg])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(egg_groups__contains=self.value())

        return queryset
