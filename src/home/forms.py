from django import forms

from core.forms import AdminModelForm
from home.models import Specimen


class SpecimenAdminForm(AdminModelForm):
    ability = forms.CharField(widget=forms.Select, required=False)

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

        if self.instance and hasattr(self.instance, "form"):
            self.fields["ability"].widget.choices = [("", "")] + [
                (a.ability, f"{a.ability}{' (hidden)' if a.is_hidden else ''}")
                for a in self.instance.form.pokemon.abilities.all()
            ]

        self._set_select_fields("language")
        self._set_select_fields("nature")
        self._set_select_fields("gender")
