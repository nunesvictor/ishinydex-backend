from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.utils.translation import ngettext
from django.views.generic import FormView

from .forms import SpecimenBulkUpdateForm


class SpecimenBulkUpdateView(FormView):
    form_class = SpecimenBulkUpdateForm
    template_name = "admin/home/specimen/bulk_change_form.html"

    def form_valid(self, form):
        specimens_queryset = form.cleaned_data["specimens"]
        update_fields = form.get_updates()

        if update_fields:
            # update() não aciona o auto_now: o updated_at vai explícito.
            updated_count = specimens_queryset.update(
                **update_fields, updated_at=timezone.now()
            )

            message = ngettext(
                "%(count)d specimen successfully updated.",
                "%(count)d specimens successfully updated.",
                updated_count,
            ) % {"count": updated_count}

            messages.success(self.request, message)
        else:
            messages.warning(self.request, _("No fields were modified for update."))

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(admin.site.each_context(self.request))
        context["title"] = _lazy("Specimen Bulk Update")

        return context

    def get_success_url(self):
        return self.request.path
