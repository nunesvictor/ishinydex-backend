"""Criação (e remoção) de PersonalDex e instalação do esquema nas boxes do
HOME.

Usado pelos comandos ``create_personal_dex``/``create_home_scheme`` e pela API
(``POST``/``DELETE /personal-dexes/``).
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from functools import reduce
from operator import or_

from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet

from pokedex.models import PokemonForm

from .models import Box, PersonalDex, Slot, Specimen

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
        PokemonForm.objects.select_related("pokemon__species")
        .filter(is_battle_only=False)
        .exclude(
            Q(pokemon__species__name__in=DEFAULT_FORM_ONLY_LIST) & Q(is_default=False)
        )
        .exclude(reduce(or_, (Q(**lookup) for lookup in DEFAULT_KWARGS_LOOKUPS), Q()))
        .exclude(*DEFAULT_EXTRA_ARGS)
    )


def _generation(form: PokemonForm) -> str | None:
    species = form.pokemon.species if form.pokemon else None
    return species.generation if species else None


def _starts_generation(forms: Sequence[PokemonForm], index: int) -> bool:
    """A forma ``forms[index]`` é de outra geração que a anterior? Vale pela
    geração da espécie, então funciona mesmo sem o inicial da geração no dex.
    A 1ª forma não conta: já começa na 1ª box."""
    return index > 0 and _generation(forms[index]) != _generation(forms[index - 1])


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
                and _starts_generation(forms, index)
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


@transaction.atomic
def delete_dex(dex: PersonalDex) -> None:
    """Apaga o dex e libera os slots dele (sem forma, sem dex e sem espécime),
    para as boxes voltarem a ficar livres para outro dex. Os espécimes
    depositados continuam no inventário, agora disponíveis."""
    Slot.objects.filter(personal_dex=dex).update(
        form=None, personal_dex=None, specimen=None
    )
    dex.delete()


def plan_specimen_links(
    dexes: Iterable[PersonalDex], *, strict: bool = False
) -> tuple[list[Slot], int]:
    """Espécimes livres (fora de qualquer slot) para os slots vazios, com forma,
    dos ``dexes``, na ordem das boxes. Prefere o brilho do dex (shiny num shiny
    dex); sem ``strict``, usa o outro quando não há. Um espécime vai para um
    slot só.

    Só atribui ``slot.specimen`` em memória (ver ``link_specimens``). Retorna
    os slots que recebem um espécime e quantos ficaram sem."""
    slots = list(
        Slot.objects.filter(
            personal_dex__in=dexes, form__isnull=False, specimen__isnull=True
        )
        .select_related("personal_dex", "box", "form__pokemon__species")
        .order_by("box__position", "position")
    )

    # Espécimes livres, agrupados por forma e brilho.
    free: defaultdict[tuple[int | None, bool], list[Specimen]] = defaultdict(list)
    for specimen in (
        Specimen.objects.filter(
            form_id__in={s.form_id for s in slots}, slot__isnull=True
        )
        .select_related("location__trainer__version")
        .order_by("id")
    ):
        free[(specimen.form_id, specimen.is_shiny)].append(specimen)

    linked, missing = [], 0
    for slot in slots:
        wanted = slot.personal_dex.is_shiny_dex
        candidates = [(slot.form_id, wanted)]
        if not strict:
            candidates.append((slot.form_id, not wanted))

        pool = next((free[key] for key in candidates if free[key]), None)
        if pool is None:
            missing += 1
            continue

        slot.specimen = pool.pop(0)
        linked.append(slot)

    return linked, missing


@transaction.atomic
def link_specimens(
    dexes: Iterable[PersonalDex], *, strict: bool = False, dry_run: bool = False
) -> tuple[list[Slot], int]:
    """Deposita os espécimes de ``plan_specimen_links``; com ``dry_run``, só
    simula (nada é salvo)."""
    linked, missing = plan_specimen_links(dexes, strict=strict)
    if not dry_run:
        Slot.objects.bulk_update(linked, ["specimen"])
    return linked, missing
