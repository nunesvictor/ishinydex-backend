from core.forms import AdminModelForm

from .models import PokemonSpecies


class PokemonSpeciesAdminForm(AdminModelForm):
    class Meta:
        model = PokemonSpecies
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_select_fields("growth_rate")
        self._set_select_fields("color")
        self._set_select_fields("shape")
        self._set_select_fields("generation")
