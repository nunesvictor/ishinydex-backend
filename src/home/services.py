"""Criação (e remoção) de PersonalDex e instalação do esquema nas boxes do
HOME.

Usado pelos comandos ``create_personal_dex``/``create_home_scheme`` e pela API
(``POST``/``DELETE /personal-dexes/``).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import reduce
from operator import or_

from django.db import transaction
from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet

from core.consts import GEN_FIRST_FORM_NAMES
from pokedex.models import PokemonForm

from .models import Box, PersonalDex, Slot

BOX_SIZE = 30

# Boxes do Pokémon HOME (plano Premium): o espelho nunca passa disso.
HOME_MAX_BOXES = 200

# Espécies que ficam só com a forma padrão.
DEFAULT_FORM_ONLY_LIST = [
    "arceus",
    "calyrex",
    "genesect",
    "koraidon",
    "miraidon",
    "mothim",
    "pichu",
    "scatterbug",
    "silvally",
    "spewpa",
]

# Formas excluídas do conjunto padrão.
DEFAULT_KWARGS_LOOKUPS = (
    {"name__icontains": "-totem"},
    {"name__iendswith": "-origin"},
    {"name__iendswith": "-power-construct"},
    {"name__iendswith": "-starter"},
    {"name__iexact": "eternatus-eternamax"},
    {"name__iexact": "greninja-battle-bond"},
    {"name__iexact": "minior-red-meteor"},
    {"name__istartswith": "calyrex-"},
    {"name__istartswith": "kyurem-"},
    {"name__istartswith": "necrozma-"},
    {"name__istartswith": "ogerpon-"},
    {"name__istartswith": "pikachu-"},
    {"name__istartswith": "rockruff-"},
)

# Alcremie: só as variações "vanilla".
DEFAULT_EXTRA_ARGS = (
    Q(pokemon__name="alcremie") & ~Q(name__istartswith="alcremie-vanilla"),
)


def default_forms() -> QuerySet[PokemonForm]:
    """Conjunto padrão de formas de um PersonalDex, na ordem do esquema."""
    return (
        PokemonForm.objects.filter(is_battle_only=False)
        .exclude(
            Q(pokemon__species__name__in=DEFAULT_FORM_ONLY_LIST) & Q(is_default=False)
        )
        .exclude(reduce(or_, (Q(**lookup) for lookup in DEFAULT_KWARGS_LOOKUPS), Q()))
        .exclude(*DEFAULT_EXTRA_ARGS)
    )


def _starts_generation(form: PokemonForm) -> bool:
    # A 1ª geração não conta: já começa na 1ª box.
    return form.name in GEN_FIRST_FORM_NAMES[1:]


def boxes_needed(forms: Sequence[PokemonForm], force_new_box: bool) -> int:
    """Quantas boxes o esquema ocupa, seguindo as mesmas regras de
    :func:`install_scheme` (com ``force_new_box``, cada geração começa no 1º
    slot de uma box)."""
    boxes = index = 0

    while index < len(forms):
        boxes += 1

        for position in range(BOX_SIZE):
            if index >= len(forms):
                break

            if force_new_box and position > 0 and _starts_generation(forms[index]):
                break

            index += 1

    return boxes


def install_scheme(
    p_dex: PersonalDex, boxes: Iterable[Box], forms: Sequence[PokemonForm]
) -> int:
    """Distribui ``forms`` pelos slots de ``boxes``, em ordem. As boxes devem vir
    com os slots pré-carregados em ordem (ver :func:`boxes_with_slots`).
    Retorna quantas formas foram instaladas."""
    index = 0
    slots_to_update = []

    for box in boxes:
        for slot in box.slots.all():
            if index >= len(forms):
                break

            current_form = forms[index]

            if (
                p_dex.force_new_box
                and not slot.is_first
                and _starts_generation(current_form)
            ):
                break

            slot.form = current_form
            slot.personal_dex = p_dex
            slots_to_update.append(slot)
            index += 1

        if index >= len(forms):
            break

    if slots_to_update:
        Slot.objects.bulk_update(slots_to_update, fields=["form", "personal_dex"])

    return index


def boxes_with_slots(boxes: QuerySet[Box]) -> QuerySet[Box]:
    return boxes.order_by("position").prefetch_related(
        Prefetch("slots", queryset=Slot.objects.order_by("position"))
    )


def free_box_runs() -> list[list[Box]]:
    """Sequências de boxes livres (nenhum slot com forma ou dex), na ordem."""
    used = Slot.objects.filter(box=OuterRef("pk")).filter(
        Q(form__isnull=False) | Q(personal_dex__isnull=False)
    )
    runs: list[list[Box]] = [[]]

    for box in Box.objects.annotate(used=Exists(used)).order_by("position"):
        if box.used:
            if runs[-1]:
                runs.append([])
        else:
            runs[-1].append(box)

    return [run for run in runs if run]


@dataclass(frozen=True)
class DexPlan:
    """Resultado da simulação de um dex padrão, antes de criá-lo."""

    forms: list[PokemonForm]
    boxes_needed: int
    largest_free_run: int
    # Boxes existentes onde o esquema começa; None: não cabe nem criando boxes.
    boxes: list[Box] | None
    # Boxes novas a criar no fim, depois de ``boxes``.
    boxes_to_create: int = 0

    @property
    def enough_space(self) -> bool:
        return self.boxes is not None


def _trailing_free_run(runs: list[list[Box]]) -> list[Box]:
    """A sequência livre que vai até a última box (vazia se a última está em
    uso): é a única que boxes novas, criadas no fim, podem continuar."""
    last = Box.objects.order_by("position").last()
    return runs[-1] if runs and runs[-1][-1] == last else []


def plan_default_dex(force_new_box: bool) -> DexPlan:
    """Usa a 1ª sequência de boxes livres que comporte o dex; se nenhuma
    comportar, completa a sequência do fim com boxes novas, sem passar de
    :data:`HOME_MAX_BOXES`."""
    forms = list(default_forms())
    needed = boxes_needed(forms, force_new_box)
    runs = free_box_runs()
    largest = max((len(r) for r in runs), default=0)
    run = next((r for r in runs if len(r) >= needed), None)

    if run is not None:
        return DexPlan(forms, needed, largest, boxes=run[:needed])

    trailing = _trailing_free_run(runs)
    missing = needed - len(trailing)

    if Box.objects.count() + missing > HOME_MAX_BOXES:
        return DexPlan(forms, needed, largest, boxes=None)

    return DexPlan(forms, needed, largest, boxes=trailing, boxes_to_create=missing)


def create_boxes(count: int) -> list[Box]:
    """Cria ``count`` boxes no fim, com os 30 slots, chamadas "HOME n" pela
    posição (pulando nomes já usados)."""
    boxes = []
    number = Box.objects.count()

    for _ in range(count):
        number += 1
        while Box.objects.filter(name=f"HOME {number}").exists():
            number += 1
        boxes.append(Box.objects.create(name=f"HOME {number}"))

    return boxes


class NotEnoughBoxes(Exception):
    def __init__(self, plan: DexPlan):
        super().__init__(plan)
        self.plan = plan


@transaction.atomic
def create_default_dex(
    name: str, *, is_shiny_dex: bool = False, force_new_box: bool = False
) -> PersonalDex:
    """Cria um PersonalDex com o conjunto padrão de formas e instala o esquema
    na primeira sequência de boxes livres que comporte todas elas (criando as
    boxes que faltarem no fim, se preciso)."""
    plan = plan_default_dex(force_new_box)

    if not plan.enough_space:
        raise NotEnoughBoxes(plan)

    dex = PersonalDex.objects.create(
        name=name, is_shiny_dex=is_shiny_dex, force_new_box=force_new_box
    )
    dex.forms.add(*plan.forms)
    new_boxes = create_boxes(plan.boxes_to_create)
    boxes = boxes_with_slots(
        Box.objects.filter(pk__in=[b.pk for b in [*plan.boxes, *new_boxes]])
    )
    install_scheme(dex, boxes, plan.forms)
    return dex


@transaction.atomic
def delete_dex(dex: PersonalDex) -> None:
    """Apaga o dex e libera os slots dele (sem forma, sem dex e sem espécime),
    para as boxes voltarem a ficar livres para outro dex. Os espécimes
    depositados continuam no inventário, agora disponíveis."""
    Slot.objects.filter(personal_dex=dex).update(
        form=None, personal_dex=None, specimen=None
    )
    dex.delete()


GENDERS = frozenset({"male", "female", "genderless"})


def allowed_genders(form: PokemonForm) -> frozenset[str]:
    """Gêneros possíveis para um espécime da forma.

    Formas por gênero (``meowstic-female``, ``oinkologne-male``...) definem o
    gênero pelo nome: a espécie nem sempre ajuda (na base importada,
    ``oinkologne`` tem ``gender_rate`` 0, "só macho"). Nas demais vale o
    ``gender_rate`` da espécie (PokéAPI): -1 sem gênero, 0 só macho, 8 só
    fêmea, 1 a 7 macho ou fêmea.
    """
    if form.name.endswith("-female"):
        return frozenset({"female"})
    if form.name.endswith("-male"):
        return frozenset({"male"})
    if form.pokemon is None or form.pokemon.species is None:
        return GENDERS

    match form.pokemon.species.gender_rate:
        case -1:
            return frozenset({"genderless"})
        case 0:
            return frozenset({"male"})
        case 8:
            return frozenset({"female"})

    return frozenset({"male", "female"})


def with_origin_version(changes: dict) -> dict:
    """Edição em lote (``QuerySet.update``, que não passa pelo ``save``): ao
    trocar o OT, o jogo de origem acompanha a versão dele."""
    if "ot" not in changes:
        return changes

    ot = changes["ot"]
    return {**changes, "origin_version": ot.version if ot else None}
