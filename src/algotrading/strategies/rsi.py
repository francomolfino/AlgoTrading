from __future__ import annotations

import numpy as np
import pandas as pd

from algotrading.strategies.common import (
    require_columns,
    signal_from_entries_exits,
    validate_positive_window,
)


def calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """Calcula RSI simple con medias moviles de ganancias y perdidas."""
    validate_positive_window("window", window)
    delta = prices.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.rolling(window=window).mean()
    average_loss = losses.rolling(window=window).mean()
    rs = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100)
    rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50)
    return rsi


def generate_rsi_signals(
    frame: pd.DataFrame,
    window: int = 14,
    oversold: float = 30,
    overbought: float = 70,
    price_column: str = "adj_close",
    signal_column: str = "signal",
) -> pd.DataFrame:
    """Long al caer por debajo de oversold; sale al superar overbought."""
    validate_positive_window("window", window)
    if not 0 <= oversold < overbought <= 100:
        raise ValueError("Se requiere 0 <= oversold < overbought <= 100.")

    require_columns(frame, ["date", price_column])
    result = frame.copy()
    result["rsi"] = calculate_rsi(result[price_column], window=window)
    entries = result["rsi"] < oversold
    exits = result["rsi"] > overbought
    result[signal_column] = signal_from_entries_exits(entries, exits)
    result.loc[result["rsi"].isna(), signal_column] = 0
    return result
