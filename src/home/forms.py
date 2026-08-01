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

        if "form_id" in self.initial or self.instance:
            choices = [("", "---------")]
            form = None

            if self.instance.pk and isinstance(self.instance, Specimen):
                instance = self.instance

                if hasattr(instance, "form") and isinstance(instance.form, PokemonForm):
                    form = instance.form

            if not form and "form_id" in self.initial:
                form = PokemonForm.objects.filter(pk=self.initial["form_id"]).first()

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
