from django.db.models import Q

from rest_framework import filters


class PokemonFromFormFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        form_id = request.query_params.get("form_id", None)

        if form_id:
            queryset = queryset.filter(forms__id=form_id)

        return queryset


def parse_bool(value: str | None) -> bool | None:
    """ "true"/"false" (e variações) → bool; qualquer outro valor → None."""
    if value is None:
        return None

    match value.strip().lower():
        case "true" | "1" | "yes":
            return True
        case "false" | "0" | "no":
            return False

    return None


class SlotFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        if personal_dex := params.get("personal_dex"):
            queryset = queryset.filter(personal_dex_id=personal_dex)

        if box := params.get("box"):
            queryset = queryset.filter(box_id=box)

        match parse_bool(params.get("registered")):
            case True:
                queryset = queryset.filter(form__isnull=False, specimen__isnull=False)
            case False:
                queryset = queryset.filter(form__isnull=False, specimen__isnull=True)

        return queryset


class SpecimenFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        if form_id := params.get("form_id"):
            queryset = queryset.filter(form_id=form_id)

        if (available := parse_bool(params.get("available"))) is not None:
            # slot_id é anotado na queryset da view
            queryset = queryset.filter(slot_id__isnull=available)

        if (is_shiny := parse_bool(params.get("is_shiny"))) is not None:
            queryset = queryset.filter(is_shiny=is_shiny)

        if search := params.get("search", "").strip():
            queryset = queryset.filter(
                Q(nickname__icontains=search) | Q(form_name__icontains=search)
            )

        return queryset


class FormSearchFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if search := request.query_params.get("search", "").strip():
            queryset = queryset.filter(name__icontains=search)

        return queryset


class TrainerSearchFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if search := request.query_params.get("search", "").strip():
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(trainer_id__icontains=search)
            )

        return queryset
