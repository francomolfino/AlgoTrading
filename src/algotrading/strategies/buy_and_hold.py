from __future__ import annotations

import pandas as pd

from algotrading.strategies.common import require_columns


def generate_buy_and_hold_signals(
    frame: pd.DataFrame,
    signal_column: str = "signal",
) -> pd.DataFrame:
    """Siempre long. El backtester compra recien en la barra siguiente."""
    require_columns(frame, ["date"])
    result = frame.copy()
    result[signal_column] = 1
    return result
