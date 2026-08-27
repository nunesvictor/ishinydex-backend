from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.translation import gettext_lazy as _

from core.forms import AdminModelForm
from home.choices import Pokeball
from home.models import Specimen
from pokedex.models import PokemonForm
from pokedex.renderers import PokeballSpriteRenderer


class ImageSelectWidget(forms.Select):
    def __init__(self, attrs=None, choices=(), image_map=None):
        super().__init__(attrs, choices)
        self.image_map = image_map or {}

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )

        if "class" in option["attrs"]:
            option["attrs"]["class"] += " select2-image-select"
        else:
            option["attrs"]["class"] = "select2-image-select"

        val_str = str(value) if value is not None else ""
        if val_str in self.image_map:
            option["attrs"]["data-image"] = self.image_map[val_str]

        return option


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

        if "ability" in self.fields:
            self.fields["ability"] = forms.TypedChoiceField(
                label=self.fields["ability"].label,
                empty_value=None,
                choices=choices,
                required=False,
                coerce=str,
            )

        if "pokeball" in self.fields:
            field_choices = self.fields["pokeball"].choices
            self.fields["pokeball"].widget = ImageSelectWidget(
                choices=field_choices,
                image_map={
                    ball.value: PokeballSpriteRenderer(ball).get_sprite_url().as_posix()
                    for ball in Pokeball
                },
                attrs={"class": "select2-image-select"},
            )


class SpecimenBulkUpdateForm(forms.ModelForm):
    specimens = forms.ModelMultipleChoiceField(
        queryset=Specimen.objects.all(),
        label="%s".capitalize() % _("specimens being updated"),
        required=True,
        widget=FilteredSelectMultiple(
            "%s".capitalize() % _("specimens"), is_stacked=False, attrs={}
        ),
    )

    class Media:
        css = {
            "all": ("admin/css/vendor/select2/select2.min.css",),
        }
        js = (
            "admin/js/vendor/jquery/jquery.min.js",
            "admin/js/jquery.init.js",
            "js/django_jquery_bridge.js",
            "admin/js/vendor/select2/select2.full.min.js",
            "js/image_select.js",
        )

    class Meta:
        model = Specimen
        exclude = [
            "form",
            "form_name",
            "nickname",
            "ability",
            "captured_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if field_name != "specimens":
                field.required = False

        if "pokeball" in self.fields:
            field_choices = self.fields["pokeball"].choices
            self.fields["pokeball"].widget = ImageSelectWidget(
                choices=field_choices,
                image_map={
                    ball.value: PokeballSpriteRenderer(ball).get_sprite_url().as_posix()
                    for ball in Pokeball
                },
                attrs={"class": "select2-image-select"},
            )
