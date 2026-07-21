from django import forms
from django.utils.translation import gettext_lazy as _

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

        self._set_select_fields("language")
        self._set_select_fields("nature")
        self._set_select_fields("gender")

        if "form_id" in self.initial or self.instance:
            form = None

            if self.instance and isinstance(self.instance, Specimen):
                instance = self.instance

                if hasattr(instance, "form") and isinstance(instance.form, PokemonForm):
                    form = instance.form

            if form is None and "form_id" in self.initial:
                form = PokemonForm.objects.filter(pk=self.initial["form_id"]).first()

            if isinstance(form, PokemonForm):
                self.fields["ability"] = forms.ChoiceField(
                    choices=[
                        ("", "---------"),
                        *[
                            (
                                str(a.ability),
                                f"{a.ability}{' (hidden)' if a.is_hidden else ''}",
                            )
                            for a in form.pokemon.abilities.all()
                        ],
                    ],
                    widget=forms.Select(),
                    label=_("ability").capitalize(),
                    required=False,
                )

        if self.instance and self.instance.ability:
            self.initial["ability"] = str(self.instance.ability)
