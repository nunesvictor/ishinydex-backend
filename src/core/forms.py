from django import forms

import pokebase


class AdminModelForm(forms.ModelForm):
    def _set_select_fields(self, field_name: str, field_slug: str = None) -> None:
        if field_slug is None:
            field_slug = field_name.replace("_", "-")

        self.fields[field_name].widget = forms.Select(
            choices=((n, n) for n in pokebase.APIResourceList(field_slug).names)
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
