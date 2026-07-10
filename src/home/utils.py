from typing import Iterable

from django.utils.translation import gettext_lazy as _


def __choices_from_range(n: int) -> tuple[tuple[int, str], ...]:
    return ((i, f"{i + 1}") for i in range(n))


def row_choices() -> tuple[tuple[int, str], ...]:
    return __choices_from_range(5)


def col_choices() -> tuple[tuple[int, str], ...]:
    return __choices_from_range(6)


def list_humanize(iterable: Iterable[int], limit=5) -> str:
    full_list = list(iterable)
    total = len(full_list)

    if total == 0:
        return "-"

    if total == 1:
        return str(full_list[0])

    if total <= limit:
        prefix_str = ", ".join(map(str, full_list[:-1]))
        return f'{prefix_str}{_(" and ")}{full_list[-1]}'

    prefix = full_list[:limit]
    suffix = total - limit

    prefix_str = ", ".join(map(str, prefix))
    suffix_str = _(" %(and_more)s%(num)d") % {"and_more": _("and +"), "num": suffix}

    return f"{prefix_str}{suffix_str}"
