from django import forms

from core.forms import AdminModelForm
from home.models import Specimen
from pokedex.models import PokemonForm


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

        form = None

        if self.instance and self.instance.pk and hasattr(self.instance, "form"):
            form = getattr(self.instance, "form", None)

        form_id = (
            self.data.get("form")
            or self.data.get("form_id")
            or self.initial.get("form_id")
        )

        if not form and form_id:
            form = PokemonForm.objects.filter(pk=form_id).first()

        choices = [("", "---------")]

        if isinstance(form, PokemonForm):
            choices.extend(
                form.pokemon.abilities.values_list("ability", "ability").order_by(
                    "ability"
                )
            )

        self.fields["ability"] = forms.TypedChoiceField(
            label=self.fields["ability"].label,
            empty_value=None,
            choices=choices,
            required=False,
            coerce=str,
        )
