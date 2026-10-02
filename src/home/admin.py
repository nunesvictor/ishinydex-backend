"""Admin padrão do Django, para acesso emergencial e debug.

Os fluxos do dia a dia ficam no app (Flutter + API); aqui só configuração
declarativa. Exceção: o que protege a integridade dos dados, como apagar um
dex liberando os slots (``delete_dex``).
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from core.admin import TimestampedAdmin
from home.services import delete_dex

from .models import (
    HOME_TRANSFER_VERSIONS,
    Box,
    OriginalTrainer,
    PersonalDex,
    Save,
    Slot,
    Specimen,
)


class SlotInline(admin.TabularInline):
    model = Slot
    can_delete = False
    extra = 0
    fields = ("position", "row", "col", "form", "personal_dex", "specimen")
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Box)
class BoxAdmin(TimestampedAdmin):
    list_display = ("name", "position")
    search_fields = ("name",)
    ordering = ("position",)
    inlines = (SlotInline,)

    # Boxes nascem pelo app/serviços, já com os 30 slots.
    def has_add_permission(self, request):
        return False


@admin.register(OriginalTrainer)
class OriginalTrainerAdmin(admin.ModelAdmin):
    list_display = ("__str__",)
    list_filter = ("version__name",)
    search_fields = ("trainer_id", "version__name", "name")
    actions = ("create_saves",)

    @admin.action(description=_("Mark as my saves"))
    def create_saves(self, request, queryset):
        """Cria o save dos OTs escolhidos que são de jogos que recebem do
        HOME e ainda não são saves; os demais são ignorados."""
        eligible = queryset.filter(
            version__name__in=HOME_TRANSFER_VERSIONS, save_file__isnull=True
        )
        created = Save.objects.bulk_create(Save(trainer=t) for t in eligible)
        self.message_user(
            request,
            _("%(created)d save(s) created; %(skipped)d trainer(s) skipped.")
            % {"created": len(created), "skipped": queryset.count() - len(created)},
        )


@admin.register(Save)
class SaveAdmin(admin.ModelAdmin):
    list_display = ("__str__", "label")
    list_select_related = ("trainer__version",)
    search_fields = ("label", "trainer__name", "trainer__trainer_id")


@admin.register(PersonalDex)
class PersonalDexAdmin(admin.ModelAdmin):
    filter_horizontal = ("forms",)
    list_display = ("name", "is_shiny_dex")
    list_filter = ("is_shiny_dex",)
    search_fields = ("name",)

    # Apagar pelo admin também libera os slots (ver home.services.delete_dex).
    def delete_model(self, request, obj):
        delete_dex(obj)

    def delete_queryset(self, request, queryset):
        for dex in queryset:
            delete_dex(dex)


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    exclude = ("position",)
    list_display = ("box", "row", "col", "form", "personal_dex", "specimen")
    list_filter = ("personal_dex", ("specimen", admin.EmptyFieldListFilter))
    list_select_related = ("box", "form", "personal_dex", "specimen")
    raw_id_fields = ("form", "specimen")
    readonly_fields = ("box", "row", "col")
    search_fields = ("box__name", "form__name")

    # Os 30 slots de cada box nascem com ela.
    def has_add_permission(self, request):
        return False


@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin):
    list_display = ("__str__", "form", "is_shiny", "ot", "location", "captured_at")
    list_filter = ("is_shiny", "is_alpha", "is_from_go", "origin_version", "location")
    list_select_related = ("form", "ot__version", "location__trainer__version")
    raw_id_fields = ("form",)
    search_fields = ("form__name", "nickname", "ot__name", "ot__trainer_id")
