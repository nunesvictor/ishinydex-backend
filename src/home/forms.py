from core.forms import AdminModelForm
from home.models import Specimen


class SpecimenAdminForm(AdminModelForm):
    class Meta:
        model = Specimen
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_select_fields("language")
        self._set_select_fields("nature")
        self._set_select_fields("gender")
