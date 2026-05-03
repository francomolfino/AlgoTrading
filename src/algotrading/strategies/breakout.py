from __future__ import annotations

import pandas as pd

from algotrading.strategies.common import (
    require_columns,
    signal_from_entries_exits,
    validate_positive_window,
)


def generate_breakout_signals(
    frame: pd.DataFrame,
    entry_window: int = 55,
    exit_window: int = 20,
    price_column: str = "adj_close",
    signal_column: str = "signal",
) -> pd.DataFrame:
    """Long en ruptura de maximos previos; sale al perder minimos previos."""
    validate_positive_window("entry_window", entry_window)
    validate_positive_window("exit_window", exit_window)
    require_columns(frame, ["date", price_column])

    result = frame.copy()
    result[f"rolling_high_{entry_window}"] = (
        result[price_column].rolling(window=entry_window).max().shift(1)
    )
    result[f"rolling_low_{exit_window}"] = (
        result[price_column].rolling(window=exit_window).min().shift(1)
    )
    high_column = f"rolling_high_{entry_window}"
    low_column = f"rolling_low_{exit_window}"

    entries = result[price_column] > result[high_column]
    exits = result[price_column] < result[low_column]
    result[signal_column] = signal_from_entries_exits(entries, exits)
    result.loc[result[[high_column, low_column]].isna().any(axis=1), signal_column] = 0
    return result
