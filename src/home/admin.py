from typing import Any
from urllib.parse import parse_qs, urlparse

from django.contrib import admin
from django.contrib.admin import ShowFacets
from django.contrib.admin.options import IS_POPUP_VAR
from django.db.models import Max
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from core.admin import TimestampedAdmin
from core.admin_mixins import CustomFieldsRendererMixin
from home.services import delete_dex
from home.views import SpecimenBulkUpdateView
from pokedex.renderers import HomeSpriteRenderer

from .admin_filters import OriginMarkListFilter, RegistrationStatusFilter
from .forms import SpecimenAdminForm
from .models import DEFAULT_POKEMON_BOX_SIZE as BOX_SIZE
from .models import (
    HOME_TRANSFER_VERSIONS,
    Box,
    OriginalTrainer,
    PersonalDex,
    Save,
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

    @admin.display(description=_("sprite"))
    def render_sprite(self, obj: Slot):  # type: ignore[override]
        p_dex = getattr(obj, "personal_dex", None)
        specimen = getattr(obj, "specimen", None)
        is_registered = False
        opt = "default"

        if isinstance(specimen, Specimen):
            opt = "shiny" if specimen.is_shiny else "default"
            is_registered = True
        elif isinstance(p_dex, PersonalDex):
            opt = "shiny" if p_dex.is_shiny_dex else "default"

        return super().render_sprite(obj, opt=opt, is_registered=is_registered)


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

    def has_add_permission(self, request):
        return False

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
    list_display = ("__str__", "label", "specimens_count")
    list_select_related = ("trainer__version",)
    search_fields = ("label", "trainer__name", "trainer__trainer_id")

    @admin.display(description=_("specimens"))
    def specimens_count(self, obj):
        return obj.specimens.count()


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

    @admin.display(description=_("forms"))
    def forms_count(self, obj):
        return obj.forms.count()

    @admin.display(description=_("slots"))
    def slots_count(self, obj):
        return obj.slot_set.count()

    # Apagar pelo admin também libera os slots (ver home.services.delete_dex).
    def delete_model(self, request, obj):
        delete_dex(obj)

    def delete_queryset(self, request, queryset):
        for dex in queryset:
            delete_dex(dex)


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
        "box",
        "row",
        "col",
    )
    search_fields = (
        "box__name",
        "row",
        "col",
        "form__name",
    )

    class Media:
        css = {"all": ("css/styles.css",)}
        js = (
            "admin/js/vendor/jquery/jquery.js",
            "admin/js/admin/RelatedObjectLookups.js",
            "js/admin_fk_pass.js",
            "js/admin_fix_focus.js",
        )

    def has_add_permission(self, request):
        return False

    @admin.display(description=_("relative position"))
    def relative_position(self, obj):
        return (obj.position - 1) % BOX_SIZE + 1

    def _is_filtered_request(self, request):
        get_params = request.GET.copy()

        ignored_params = ["box__id__exact", "p", "o", "ot", "_facets", "q"]

        for param in ignored_params:
            if param == "q":
                if not get_params.get("q"):
                    get_params.pop("q", None)
            else:
                get_params.pop(param, None)

        return bool(get_params)

    def _is_list_request(self, request):
        if not request.resolver_match:
            return False

        return request.resolver_match.url_name.endswith("_changelist")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        boxes = list(Box.objects.only("id", "name").order_by("id"))
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
        if not selected_box_id and boxes:
            selected_box_id = str(boxes[0].id)

        is_filtered = self._is_filtered_request(request)

        extra_context["panels"] = panels
        extra_context["selected_box_id"] = selected_box_id
        extra_context["is_filtered"] = is_filtered

        if not is_filtered and selected_box_id:
            slots = list(
                Slot.objects.filter(box_id=selected_box_id)
                .select_related("form", "specimen", "personal_dex", "box")
                .order_by("position")[:30]
            )
            for slot in slots:
                # Atributo só para o template da grade.
                setattr(slot, "rendered_sprite", self.render_sprite(slot))

            extra_context["grid_slots"] = slots

        # Muda o atributo de classe por requisição: o ChangeList só lê
        # ``show_facets`` e o Django não tem um ``get_show_facets``.
        show_facets = ShowFacets.ALWAYS if is_filtered else ShowFacets.NEVER
        self.show_facets = show_facets  # type: ignore[misc]
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if not self._is_list_request(request):
            return qs

        selected_box_id = request.GET.get("box__id__exact")
        is_filtered = self._is_filtered_request(request)

        if is_filtered:
            return qs

        if not selected_box_id:
            first_box = Box.objects.order_by("id").values_list("id", flat=True).first()
            if first_box:
                selected_box_id = str(first_box)

        if selected_box_id:
            return qs.filter(box_id=selected_box_id)

        return qs

    def _get_box_id(self, request):
        referer = request.META.get("HTTP_REFERER", "")
        if referer:
            parsed = urlparse(referer)
            query_params = parse_qs(parsed.query)
            box_ids = query_params.get("box__id__exact")
            if box_ids:
                return box_ids[0]
        return None

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        context["show_save_as_new"] = False
        context["show_save_and_add_another"] = False

        show_move_on = False

        if change and obj and obj.box_id:
            last_slot = (
                obj.__class__.objects.filter(box_id=obj.box_id, form__isnull=False)
                .aggregate(max_pos=Max("position"))
                .get("max_pos")
            )

            if last_slot is not None and obj.position < last_slot:
                show_move_on = True

        context["show_save_and_move_on"] = show_move_on

        box_id = request.GET.get("box__id__exact") or self._get_box_id(request)

        context["selected_box_id"] = box_id

        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_change(self, request, obj):
        box_id = (
            request.POST.get("_box_id_filter")
            or request.GET.get("box__id__exact")
            or self._get_box_id(request)
        )

        box_param = f"?box__id__exact={box_id}" if box_id else ""

        if "_moveon" in request.POST:
            next_obj = (
                Slot.objects.filter(box=obj.box, position__gt=obj.position)
                .order_by("position")
                .first()
            )

            if not next_obj:
                next_obj = (
                    Slot.objects.filter(box_id__gt=obj.box_id)
                    .order_by("box_id", "position")
                    .first()
                )

            if next_obj:
                opts = self.opts
                redirect_url = (
                    reverse(
                        f"admin:{opts.app_label}_{opts.model_name}_change",
                        args=[next_obj.id],
                    )
                    + box_param
                )
                return HttpResponseRedirect(redirect_url)

            changelist_url = (
                reverse(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"
                )
                + box_param
            )
            return HttpResponseRedirect(changelist_url)

        response = super().response_change(request, obj)

        if (
            isinstance(response, HttpResponseRedirect)
            and not response.url.endswith("/change/")
            and "_continue" not in request.POST
        ):
            changelist_url = (
                reverse(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"
                )
                + box_param
            )
            return HttpResponseRedirect(changelist_url)

        return response

    def registration_status(self, obj):
        return obj.specimen_id is not None

    def render_sprite(self, obj: Slot):  # type: ignore[override]
        specimen = getattr(obj, "specimen", None)
        p_dex = getattr(obj, "personal_dex", None)
        is_registered = False
        opt = "default"

        if specimen:
            opt = "shiny" if specimen.is_shiny else "default"
            is_registered = True
        elif p_dex:
            opt = "shiny" if p_dex.is_shiny_dex else "default"

        return super().render_sprite(obj, opt=opt, is_registered=is_registered)


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
        "origin_version",
        "is_shiny",
        "is_alpha",
        "is_from_go",
        "captured_at",
        "pokeball",
        "observation",
    ]
    inlines = [SlotInline]
    list_display = (
        "render_sprite",
        "render_label",
        "render_gender",
        "nature",
        "ability",
        "is_shiny",
        "is_alpha",
        "language",
        "ot",
        "captured_at",
    )
    list_filter = (
        OriginMarkListFilter,
        "ot",
        "gender",
        "nature",
        "is_alpha",
        "is_shiny",
        "is_from_go",
    )
    search_fields = (
        "form__name",
        "nickname",
        "ability",
        "nature",
        "ot__trainer_id",
        "=captured_at",
    )
    show_facets = admin.ShowFacets.ALWAYS

    class Media:
        css = {
            "all": ("admin/css/vendor/select2/select2.min.css",),
        }
        js = (
            "admin/js/vendor/jquery/jquery.min.js",
            "admin/js/jquery.init.js",
            "admin/js/vendor/select2/select2.full.min.js",
            "js/image_select.js",
            "js/admin_load_abilities.js",
        )

    def get_changeform_initial_data(self, request):
        initial: dict[str, Any] = super().get_changeform_initial_data(request)

        if "form_id" in request.GET:
            initial["form"] = request.GET["form_id"]
        if "personal_dex_id" in request.GET:
            personal_dex_id = request.GET["personal_dex_id"]
            p_dex = PersonalDex.objects.filter(id=personal_dex_id).first()

            initial["is_shiny"] = bool(p_dex and p_dex.is_shiny_dex)

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
                ("captured_at", "pokeball"),
                ("is_shiny", "is_alpha", "is_from_go"),
            ]

            if "nickname" in fields:
                fields.remove("nickname")
            if "language" in fields:
                fields.remove("language")

        return fields

    def get_inlines(self, request, obj=None):
        # Lista nova: o ``get_inlines`` padrão devolve o próprio
        # ``self.inlines``, e esvaziá-lo valeria para todas as requisições.
        if IS_POPUP_VAR in request.GET:
            return []

        return super().get_inlines(request, obj)

    def get_urls(self):
        urls = super().get_urls()
        info = self.opts.app_label, self.opts.model_name

        custom_urls = [
            path(
                "bulk-update/",
                self.admin_site.admin_view(SpecimenBulkUpdateView.as_view()),
                name="%s_%s_bulk_update" % info,
            ),
        ]

        return custom_urls + urls

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
    def render_sprite(self, obj: Specimen):  # type: ignore[override]
        opt = "shiny" if obj.is_shiny else "default"

        return super().render_sprite(
            obj.form, opt=opt, is_registered=True, renderer=HomeSpriteRenderer
        )
