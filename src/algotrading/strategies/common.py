from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")


def validate_positive_window(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor a cero.")


def signal_from_entries_exits(entries: pd.Series, exits: pd.Series) -> pd.Series:
    """Convierte eventos de entrada/salida en una posicion persistente 0/1."""
    if len(entries) != len(exits):
        raise ValueError("entries y exits deben tener la misma longitud.")

    in_position = False
    values: list[int] = []
    for entry, exit_ in zip(entries.fillna(False), exits.fillna(False), strict=True):
        if in_position and bool(exit_):
            in_position = False
        if not in_position and bool(entry):
            in_position = True
        values.append(1 if in_position else 0)

    return pd.Series(values, index=entries.index, dtype=int)
