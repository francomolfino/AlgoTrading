from __future__ import annotations

import pandas as pd

from algotrading.analysis.exploration import add_moving_averages
from algotrading.strategies.common import require_columns, validate_positive_window


def generate_trend_filter_signals(
    frame: pd.DataFrame,
    fast_window: int = 20,
    slow_window: int = 100,
    trend_window: int = 200,
    price_column: str = "adj_close",
    signal_column: str = "signal",
) -> pd.DataFrame:
    """Cruce de medias habilitado solo si el precio esta sobre su tendencia larga."""
    validate_positive_window("fast_window", fast_window)
    validate_positive_window("slow_window", slow_window)
    validate_positive_window("trend_window", trend_window)
    if fast_window >= slow_window:
        raise ValueError("fast_window debe ser menor que slow_window.")

    require_columns(frame, ["date", price_column])
    result = add_moving_averages(
        frame,
        windows=sorted({fast_window, slow_window, trend_window}),
        price_column=price_column,
    )
    fast_column = f"sma_{fast_window}"
    slow_column = f"sma_{slow_window}"
    trend_column = f"sma_{trend_window}"

    result[signal_column] = (
        (result[fast_column] > result[slow_column])
        & (result[price_column] > result[trend_column])
    ).astype(int)
    result.loc[result[[fast_column, slow_column, trend_column]].isna().any(axis=1), signal_column] = 0
    return result
