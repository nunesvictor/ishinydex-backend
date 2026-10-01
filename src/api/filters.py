from datetime import date
from functools import reduce
from operator import or_

from django.db.models import (
    BooleanField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)
from django.db.models.functions import Coalesce

from rest_framework import filters

from home.models import DEFAULT_POKEMON_BOX_SIZE, Slot
from home.origin_marks import origin_mark_q
from pokedex.models import (
    FORM_NATIONAL_ORDERING,
    PokemonAbility,
    PokemonForm,
    PokemonFormType,
    PokemonSpeciesDexEntry,
    ShinyLock,
)


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


def search_forms(search: str) -> QuerySet[PokemonForm]:
    """Formas por nome (``icontains``) ou, se ``search`` for um número, pelo
    número da Pokédex nacional da espécie ou pelo ``pokeapi_id`` da forma (o
    número que o app mostra)."""
    if not search.isdigit():
        return PokemonForm.objects.filter(name__icontains=search)

    number = int(search)
    return PokemonForm.objects.filter(
        Q(pokeapi_id=number)
        | Q(
            pokemon__species__pokedex_numbers__pokedex="national",
            pokemon__species__pokedex_numbers__entry_number=number,
        )
    )


class SlotFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        if personal_dex := params.get("personal_dex"):
            queryset = queryset.filter(personal_dex_id=personal_dex)

        if box := params.get("box"):
            queryset = queryset.filter(box_id=box)

        if search := params.get("search", "").strip():
            queryset = queryset.filter(form__in=search_forms(search))

        match parse_bool(params.get("registered")):
            case True:
                queryset = queryset.filter(form__isnull=False, specimen__isnull=False)
            case False:
                queryset = queryset.filter(form__isnull=False, specimen__isnull=True)

        return queryset


# Parâmetro → campo, para filtros de lista simples (valores por vírgula).
SPECIMEN_LIST_FILTERS = {
    "generation": "form__pokemon__species__generation",
    "gender": "gender",
    "nature": "nature",
    "language": "language",
}


def _first_slot_key(slots: QuerySet[Slot]) -> Subquery:
    """Posição do 1º slot de ``slots`` nas boxes, como um número só: box,
    depois linha e coluna."""
    key = (
        F("box__position") * DEFAULT_POKEMON_BOX_SIZE
        + F("row") * 6  # 6 colunas por linha
        + F("col")
    )
    return Subquery(slots.annotate(key=key).order_by("key").values("key")[:1])


def box_order() -> Coalesce:
    """Onde o espécime fica nas boxes: o próprio slot, se depositado; senão o
    1º slot (menor box) com a forma dele, em qualquer dex. ``None`` se a
    forma não está em nenhuma box."""
    return Coalesce(
        _first_slot_key(Slot.objects.filter(specimen=OuterRef("pk"))),
        _first_slot_key(Slot.objects.filter(form=OuterRef("form"))),
    )


def national_order() -> Subquery:
    """Nº da espécie do espécime na Pokédex nacional (``None`` se não há)."""
    return Subquery(
        PokemonSpeciesDexEntry.objects.filter(
            pokedex="national",
            pokemon_species=OuterRef("form__pokemon__species"),
        ).values("entry_number")[:1]
    )


# Valor de ``ordering`` → (anotações, ``order_by``). A ordem canônica da forma
# desempata formas no mesmo lugar (ex.: as da mesma espécie) e ``pk``, a
# paginação.
FORM_TIEBREAK = tuple(f"form__{field}" for field in FORM_NATIONAL_ORDERING[:-1])
SPECIMEN_ORDERINGS = {
    "box": (
        {"box_order": box_order},
        (F("box_order").asc(nulls_last=True), *FORM_TIEBREAK, "pk"),
    ),
    "national": (
        {"national_order": national_order},
        (F("national_order").asc(nulls_last=True), *FORM_TIEBREAK, "pk"),
    ),
    "captured_at": ({}, (F("captured_at").asc(nulls_last=True), "pk")),
    "-captured_at": ({}, (F("captured_at").desc(nulls_last=True), "-pk")),
    "-created_at": ({}, ("-created_at", "-pk")),
}
DEFAULT_SPECIMEN_ORDERING = "box"


def parse_list(value: str | None) -> list[str]:
    """ "a, b,,c" → ["a", "b", "c"]."""
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def parse_date(value: str) -> date | None:
    """Data ISO (``AAAA-MM-DD``); valor inválido → None (filtro ignorado)."""
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def with_none(condition: Q, values: list[str], none_condition: Q) -> Q:
    """Soma ``none_condition`` à condição quando ``values`` contém "none"."""
    return condition | none_condition if "none" in values else condition


class SpecimenFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        if form_id := params.get("form_id"):
            queryset = queryset.filter(form_id=form_id)

        # Ids escolhidos (ex.: "só selecionados" do lote no app).
        if ids := parse_list(params.get("id")):
            queryset = queryset.filter(pk__in=[i for i in ids if i.isdigit()])

        if (available := parse_bool(params.get("available"))) is not None:
            # slot_id é anotado na queryset da view
            queryset = queryset.filter(slot_id__isnull=available)

        for flag in ("is_shiny", "is_alpha", "is_from_go"):
            if (value := parse_bool(params.get(flag))) is not None:
                queryset = queryset.filter(**{flag: value})

        if search := params.get("search", "").strip():
            queryset = queryset.filter(
                Q(form__in=search_forms(search))
                if search.isdigit()
                else Q(nickname__icontains=search) | Q(form_name__icontains=search)
            )

        if balls := parse_list(params.get("pokeball")):
            queryset = queryset.filter(
                with_none(Q(pokeball__in=balls), balls, Q(pokeball__isnull=True))
            )

        if ots := parse_list(params.get("ot")):
            ids = [ot for ot in ots if ot.isdigit()]
            queryset = queryset.filter(
                with_none(Q(ot_id__in=ids), ots, Q(ot__isnull=True))
            )

        # Marcas somam (OU): "paldea,go" traz os dois.
        if marks := parse_list(params.get("origin_mark")):
            queryset = queryset.filter(reduce(or_, map(origin_mark_q, marks)))

        # Com mais de um tipo, a forma precisa ter todos (ex.: água + voador).
        for type_ in parse_list(params.get("type")):
            queryset = queryset.filter(form__types__type=type_)

        for param, field in SPECIMEN_LIST_FILTERS.items():
            if values := parse_list(params.get(param)):
                queryset = queryset.filter(**{f"{field}__in": values})

        if ability := params.get("ability", "").strip():
            queryset = queryset.filter(ability__icontains=ability)

        if after := parse_date(params.get("captured_after", "")):
            queryset = queryset.filter(captured_at__gte=after)

        if before := parse_date(params.get("captured_before", "")):
            queryset = queryset.filter(captured_at__lte=before)

        # Valor desconhecido (inclusive o antigo "dex") → ordem das boxes.
        annotations, ordering = SPECIMEN_ORDERINGS.get(
            params.get("ordering", ""),
            SPECIMEN_ORDERINGS[DEFAULT_SPECIMEN_ORDERING],
        )
        queryset = queryset.annotate(
            **{name: build() for name, build in annotations.items()}
        )
        return queryset.order_by(*ordering)


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


# Lista de caçadas (GET /personal-dexes/{id}/hunts/). Motivos são somados
# (OU); escopo (geração, tipo, categoria, busca) restringe (E).
HUNT_REASONS = ("no_shiny", "from_go", "pokeball")
HUNT_DEFAULT_REASONS = ("no_shiny",)
HUNT_CATEGORIES = ("legendary", "mythical", "ultra-beast", "baby", "regular")
# A PokéAPI não marca Ultra Beasts; a Beast Boost é exclusiva delas.
ULTRA_BEAST_ABILITY = "beast-boost"
SPECIES = "form__pokemon__species__"


def as_bool(condition: Q) -> ExpressionWrapper:
    return ExpressionWrapper(condition, output_field=BooleanField())


def has_lock(lock_type: str) -> Exists:
    return Exists(
        ShinyLock.objects.filter(
            forms=OuterRef("form"), active=True, lock_type=lock_type
        )
    )


def hunt_reason_conditions(accepted_balls: list[str]) -> dict[str, Q]:
    """Condição de cada motivo. ``pokeball`` só existe com bolas aceitas, e
    espécime sem pokébola informada não conta como bola errada."""
    shiny = Q(specimen__is_shiny=True)
    conditions = {
        "no_shiny": Q(specimen__isnull=True) | Q(specimen__is_shiny=False),
        "from_go": shiny & Q(specimen__is_from_go=True),
    }
    if accepted_balls:
        conditions["pokeball"] = (
            shiny
            & Q(specimen__pokeball__isnull=False)
            & ~Q(specimen__pokeball__in=accepted_balls)
        )
    return conditions


def hunt_category_conditions() -> dict[str, Q]:
    """Condição de cada categoria; requer a anotação ``is_ultra_beast``."""
    special = {
        "legendary": Q(**{f"{SPECIES}is_legendary": True}),
        "mythical": Q(**{f"{SPECIES}is_mythical": True}),
        "ultra-beast": Q(is_ultra_beast=True),
        "baby": Q(**{f"{SPECIES}is_baby": True}),
    }
    regular = Q(**{f"{SPECIES}isnull": False})
    for condition in special.values():
        regular &= ~condition
    return special | {"regular": regular}


def filter_hunts(queryset: QuerySet, params) -> QuerySet:
    """Slots (com forma) de um shiny dex que ainda precisam ser caçados.

    Anota ``hunt_<motivo>`` para cada motivo possível (a resposta traz todos
    em que o slot se encaixa, não só os pedidos) e ``hunt_unobtainable`` /
    ``hunt_distro_only`` (shiny lock)."""
    conditions = hunt_reason_conditions(parse_list(params.get("accepted_balls")))
    queryset = queryset.filter(form__isnull=False).annotate(
        **{f"hunt_{name}": as_bool(cond) for name, cond in conditions.items()},
        hunt_unobtainable=has_lock(ShinyLock.LockTypeChoices.UNOBTAINABLE),
        hunt_distro_only=has_lock(ShinyLock.LockTypeChoices.DISTRO_ONLY),
        is_ultra_beast=Exists(
            PokemonAbility.objects.filter(
                pokemons=OuterRef("form__pokemon"), ability=ULTRA_BEAST_ABILITY
            )
        ),
    )

    # Sem ``reasons``, o padrão; motivos desconhecidos são ignorados.
    requested = (
        parse_list(params.get("reasons"))
        if "reasons" in params
        else HUNT_DEFAULT_REASONS
    )
    wanted = Q(pk__in=[])
    for reason in requested:
        if reason in conditions:
            wanted |= conditions[reason]
    queryset = queryset.filter(wanted)

    if not parse_bool(params.get("include_locked")):
        queryset = queryset.filter(hunt_unobtainable=False)

    if generations := parse_list(params.get("generation")):
        queryset = queryset.filter(**{f"{SPECIES}generation__in": generations})

    # Qualquer um dos tipos (diferente de /specimens/, que exige todos).
    if types := parse_list(params.get("type")):
        queryset = queryset.filter(
            Exists(
                PokemonFormType.objects.filter(
                    pokemon_forms=OuterRef("form"), type__in=types
                )
            )
        )

    categories = hunt_category_conditions()
    if chosen := [c for c in parse_list(params.get("category")) if c in categories]:
        condition = Q(pk__in=[])
        for category in chosen:
            condition |= categories[category]
        queryset = queryset.filter(condition)

    if search := params.get("search", "").strip():
        queryset = queryset.filter(form__in=search_forms(search))

    return queryset
