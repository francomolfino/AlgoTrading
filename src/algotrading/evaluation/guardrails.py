from __future__ import annotations

from collections.abc import Mapping, Sequence


def count_parameter_combinations(grid: Mapping[str, Sequence[object]]) -> int:
    """Cuenta combinaciones para evitar optimizaciones enormes por accidente."""
    total = 1
    for name, values in grid.items():
        if not values:
            raise ValueError(f"El parametro {name} no tiene valores.")
        total *= len(values)
    return total


def validate_parameter_grid_size(
    grid: Mapping[str, Sequence[object]],
    max_combinations: int = 30,
) -> int:
    """Falla si el grid es demasiado grande para una busqueda educativa."""
    if max_combinations <= 0:
        raise ValueError("max_combinations debe ser mayor a cero.")

    total = count_parameter_combinations(grid)
    if total > max_combinations:
        raise ValueError(
            f"Grid demasiado grande: {total} combinaciones. "
            f"Limite educativo: {max_combinations}."
        )
    return total
