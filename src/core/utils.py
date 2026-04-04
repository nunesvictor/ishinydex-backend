def __choices_from_range(n: int) -> tuple[tuple[int, str], ...]:
    return ((i, f"{i + 1}") for i in range(n))


def row_choices() -> tuple[tuple[int, str], ...]:
    return __choices_from_range(5)


def col_choices() -> tuple[tuple[int, str], ...]:
    return __choices_from_range(6)
