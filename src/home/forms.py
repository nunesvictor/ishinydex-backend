from django import forms
from django.utils.translation import gettext_lazy as _

from core.forms import AdminModelForm
from home.models import Specimen


class SpecimenAdminForm(AdminModelForm):
    class Meta:
        model = Specimen
        fields = "__all__"
        widgets = {
            "captured_at": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_select_fields("language")
        self._set_select_fields("nature")
        self._set_select_fields("gender")

        if self.instance and hasattr(self.instance, "form") and self.instance.form:
            ability_choices = [("", "---------")] + [
                (str(a.ability), f"{a.ability}{' (hidden)' if a.is_hidden else ''}")
                for a in self.instance.form.pokemon.abilities.all()
            ]

            self.fields["ability"] = forms.ChoiceField(
                choices=ability_choices,
                widget=forms.Select(),
                label=_("ability").capitalize(),
                required=False,
            )

            if self.instance.ability:
                self.initial["ability"] = str(self.instance.ability)
