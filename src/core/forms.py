from django import forms


class AdminModelForm(forms.ModelForm):
    def _set_select_fields(self, field_name: str) -> None:
        """Troca o campo de texto por um select com os valores já cadastrados.

        As opções vêm do próprio banco (importado da PokéAPI), então o form
        funciona offline e não faz requisições a cada abertura.
        """
        if field_name not in self.fields:
            return

        values = set(
            self._meta.model.objects.exclude(**{field_name: ""})
            .values_list(field_name, flat=True)
            .distinct()
        )
        current = getattr(self.instance, field_name, None)

        if current:
            values.add(current)

        choices = [("", "---------"), *((v, v) for v in sorted(values))]
        self.fields[field_name].widget = forms.Select(choices=choices)
