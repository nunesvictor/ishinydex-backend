from rest_framework import filters


class PokemonFromFormFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        form_id = request.query_params.get("form_id", None)

        if form_id:
            queryset = queryset.filter(forms__id=form_id)

        return queryset
