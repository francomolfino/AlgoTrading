from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def add_daily_returns(
    frame: pd.DataFrame,
    price_column: str = "adj_close",
    output_column: str = "daily_return",
) -> pd.DataFrame:
    """Agrega retornos diarios simples: precio_t / precio_t-1 - 1."""
    _require_columns(frame, ["date", price_column])
    result = frame.copy()
    result[output_column] = result[price_column].pct_change(fill_method=None)
    return result


def add_moving_averages(
    frame: pd.DataFrame,
    windows: Iterable[int],
    price_column: str = "adj_close",
    prefix: str = "sma",
) -> pd.DataFrame:
    """Agrega medias moviles simples para las ventanas indicadas."""
    _require_columns(frame, ["date", price_column])
    result = frame.copy()

    for window in windows:
        if window <= 0:
            raise ValueError(f"La ventana debe ser positiva: {window}")
        result[f"{prefix}_{window}"] = result[price_column].rolling(window=window).mean()

    return result


def prepare_exploration_frame(
    frame: pd.DataFrame,
    windows: Iterable[int] = (20, 50, 200),
    price_column: str = "adj_close",
) -> pd.DataFrame:
    """Prepara datos de Etapa 2 con retornos diarios y medias moviles."""
    result = frame.sort_values("date").reset_index(drop=True)
    result = add_daily_returns(result, price_column=price_column)
    result = add_moving_averages(result, windows=windows, price_column=price_column)
    return result


def summarize_exploration(
    frame: pd.DataFrame,
    price_column: str = "adj_close",
) -> dict[str, float | int | str]:
    """Devuelve un resumen numerico chico para imprimir en CLI."""
    _require_columns(frame, ["date", price_column, "daily_return"])
    clean_returns = frame["daily_return"].dropna()

    first_price = float(frame[price_column].iloc[0])
    last_price = float(frame[price_column].iloc[-1])
    total_return = (last_price / first_price) - 1

    return {
        "start_date": frame["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": frame["date"].iloc[-1].strftime("%Y-%m-%d"),
        "rows": int(len(frame)),
        "first_price": first_price,
        "last_price": last_price,
        "total_return": float(total_return),
        "average_daily_return": float(clean_returns.mean()),
        "best_daily_return": float(clean_returns.max()),
        "worst_daily_return": float(clean_returns.min()),
    }


def moving_average_columns(windows: Iterable[int], prefix: str = "sma") -> list[str]:
    return [f"{prefix}_{window}" for window in windows]


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
