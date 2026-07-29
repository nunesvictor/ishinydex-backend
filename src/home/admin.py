from django.contrib import admin
from django.contrib.admin.options import IS_POPUP_VAR
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.admin import TimestampedAdmin
from core.admin_mixins import CustomFieldsRendererMixin
from pokedex.renderers import HomeSpriteRenderer

from .admin_filters import RegistrationStatusFilter
from .forms import SpecimenAdminForm
from .models import DEFAULT_POKEMON_BOX_SIZE as BOX_SIZE
from .models import (
    Box,
    OriginalTrainer,
    PersonalDex,
    Slot,
    Specimen,
)
from .utils import list_humanize


class SlotInline(admin.TabularInline, CustomFieldsRendererMixin):
    model = Slot
    can_delete = False
    extra = 0
    fields = (
        "render_sprite",
        "position",
        "row",
        "col",
        "specimen",
    )
    raw_id_fields = ("specimen",)
    readonly_fields = ("render_sprite", "position", "row", "col")
    show_change_link = True

    class Media:
        css = {"all": ("css/styles.css",)}

    def render_sprite(self, obj: Slot):
        p_dex = getattr(obj, "personal_dex", None)
        specimen = getattr(obj, "specimen", None)
        is_registered = False
        is_shiny = False

        if isinstance(specimen, Specimen):
            is_shiny = specimen.is_shiny
            is_registered = True
        elif isinstance(p_dex, PersonalDex):
            is_shiny = p_dex.is_shiny_dex

        return super().render_sprite(
            opt="shiny" if is_shiny else "default",
            renderer=HomeSpriteRenderer,
            is_registered=is_registered,
            obj=obj,
        )

    render_sprite.short_description = _("sprite")


@admin.register(Box)
class BoxAdmin(TimestampedAdmin):
    list_display = (
        "name",
        "position",
        "is_schema_configured",
        "is_schema_filled_out",
        "empty_slots",
    )
    search_fields = ("name",)
    ordering = ("position",)
    inlines = (SlotInline,)

    @admin.display(boolean=True, description=_("is schema configured"))
    def is_schema_configured(self, obj):
        return any([s.personal_dex for s in obj.slots.all()])

    @admin.display(boolean=True, description=_("is schema filled out"))
    def is_schema_filled_out(self, obj):
        if not self.is_schema_configured(obj) or obj.slots.count() == 0:
            return False

        return not obj.slots.filter(form__isnull=False, specimen__isnull=True).exists()

    @admin.display(description=_("empty slots"))
    def empty_slots(self, obj):
        return list_humanize(
            [
                ((s.position - 1) % BOX_SIZE) + 1
                for s in obj.slots.filter(form__isnull=False, specimen__isnull=True)
            ],
        )


@admin.register(OriginalTrainer)
class OriginalTrainerAdmin(admin.ModelAdmin):
    list_display = ("__str__",)
    list_filter = ("version__name",)
    search_fields = ("trainer_id", "version__name", "name")


@admin.register(PersonalDex)
class PersonalDexAdmin(admin.ModelAdmin):
    filter_horizontal = ("forms",)
    list_display = (
        "name",
        "is_shiny_dex",
        "forms_count",
        "slots_count",
    )
    list_filter = ("is_shiny_dex",)
    search_fields = ("name",)

    def forms_count(self, obj):
        return obj.forms.count()

    def slots_count(self, obj):
        return obj.slot_set.count()

    forms_count.short_description = _("forms")
    slots_count.short_description = _("slots")


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
    exclude = ("position",)
    list_display = (
        "render_sprite",
        "form",
        "specimen",
        "personal_dex",
        "box",
        "row",
        "col",
        "relative_position",
    )
    list_filter = (
        "personal_dex",
        RegistrationStatusFilter,
        "specimen__is_alpha",
        "specimen__is_shiny",
        "specimen__is_from_go",
        "row",
        "col",
    )
    list_per_page = 30
    readonly_fields = (
        "row",
        "col",
    )
    search_fields = (
        "box__name",
        "row",
        "col",
        "form__name",
    )
    show_facets = admin.ShowFacets.ALWAYS

    class Media:
        css = {"all": ("css/styles.css",)}
        js = (
            "admin/js/vendor/jquery/jquery.js",
            "admin/js/admin/RelatedObjectLookups.js",
            "js/admin_fk_pass.js",
            "js/admin_fix_focus.js",
        )

    @admin.display(description=_("relative position"))
    def relative_position(self, obj):
        return (obj.position - 1) % BOX_SIZE + 1

    def changelist_view(self, request, extra_context=None):
        boxes = list(Box.objects.all().order_by("id"))
        extra_context = extra_context or {}
        chunk_size = 30
        panels = []

        for i in range(0, len(boxes), chunk_size):
            panel_boxes = boxes[i : i + chunk_size]
            start_num = i + 1
            end_num = i + len(panel_boxes)
            panels.append(
                {"label": f"Boxes {start_num}-{end_num}", "boxes": panel_boxes}
            )

        selected_box_id = request.GET.get("box__id__exact")
        extra_context["panels"] = panels

        if not selected_box_id and boxes:
            selected_box_id = str(boxes[0].id)

        extra_context["selected_box_id"] = selected_box_id

        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        selected_box_id = request.GET.get("box__id__exact")

        if not selected_box_id:
            first_box = Box.objects.first()
            if first_box:
                selected_box_id = first_box.id

        if selected_box_id:
            return qs.filter(box_id=selected_box_id)

        return qs

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        context["show_save_as_new"] = False
        context["show_save_and_add_another"] = False
        context["show_save_and_move_on"] = True
        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_change(self, request, obj):
        response = super().response_change(request, obj)

        if "_moveon" in request.POST:
            next_obj = Slot.objects.filter(id__gt=obj.id).order_by("id").first()
            return HttpResponseRedirect(
                reverse("admin:home_slot_change", args=[next_obj.id])
            )

        return response

    def registration_status(self, obj):
        return obj.specimen is not None

    def render_sprite(self, obj: Slot):
        p_dex = getattr(obj, "personal_dex", None)
        specimen = getattr(obj, "specimen", None)
        is_registered = False
        is_shiny = False

        if isinstance(specimen, Specimen):
            is_shiny = specimen.is_shiny
            is_registered = True
        elif isinstance(p_dex, PersonalDex):
            is_shiny = p_dex.is_shiny_dex

        return super().render_sprite(
            opt="shiny" if is_shiny else "default",
            renderer=HomeSpriteRenderer,
            is_registered=is_registered,
            obj=obj,
        )


@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin, CustomFieldsRendererMixin):
    form = SpecimenAdminForm
    fields = [
        "form",
        "nickname",
        "language",
        "gender",
        "nature",
        "ability",
        "ot",
        "is_shiny",
        "is_alpha",
        "is_from_go",
        "captured_at",
        "observation",
    ]
    inlines = [SlotInline]
    list_display = (
        "render_sprite",
        "render_label",
        "ability",
        "language",
        "render_gender",
        "nature",
        "is_alpha",
        "is_shiny",
        "ot",
        "captured_at",
    )
    list_filter = ("language", "gender", "is_alpha", "is_shiny", "ot")
    search_fields = (
        "form__name",
        "nickname",
        "ability",
        "nature",
        "ot__trainer_id",
        "captured_at",
    )
    show_facets = admin.ShowFacets.ALWAYS

    class Media:
        js = ("js/admin_load_abilities.js",)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)

        if "form_id" in request.GET:
            initial["form"] = request.GET["form_id"]
        if "personal_dex_id" in request.GET:
            personal_dex_id = request.GET["personal_dex_id"]
            p_dex = PersonalDex.objects.filter(id=personal_dex_id).first()

            initial["is_shiny"] = p_dex and p_dex.is_shiny_dex

        return initial

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)

        if IS_POPUP_VAR in request.GET:
            fields = [
                "form",
                "nickname",
                ("gender", "nature"),
                "ability",
                "language",
                "ot",
                "captured_at",
                ("is_shiny", "is_alpha", "is_from_go"),
            ]

            if "nickname" in fields:
                fields.remove("nickname")
            if "language" in fields:
                fields.remove("language")

        return fields

    def get_inlines(self, request, obj=None):
        inlines = super().get_inlines(request, obj)

        if IS_POPUP_VAR in request.GET:
            inlines.clear()

        return inlines

    @admin.display(description=_("nickname or form"))
    def render_label(self, obj):
        return obj.nickname if obj.nickname else obj.form.name

    @admin.display(description=_("gender"))
    def render_gender(self, obj):
        if obj.gender == "male":
            return "♂️"
        elif obj.gender == "female":
            return "♀️"

        return "-"

    @admin.display(description=_("sprite"))
    def render_sprite(self, obj: Specimen):
        return super().render_sprite(
            opt="shiny" if obj.is_shiny else "default",
            renderer=HomeSpriteRenderer,
            is_registered=True,
            obj=obj.form,
        )
