from __future__ import annotations

import pandas as pd
import streamlit as st


def render_signal_reading(strategy_key: str, summary: dict[str, int | float], rows: int) -> None:
    entries = int(summary["entries"])
    exposure = float(summary["exposure_ratio"])
    if entries == 0:
        st.warning("Esta configuracion no genera entradas en el periodo. El backtest no va a decir mucho.")
    elif entries < 5 and strategy_key != "buy_and_hold":
        st.warning("Pocas entradas: la muestra de trades probablemente sera debil.")
    if exposure > 0.95 and strategy_key != "buy_and_hold":
        st.warning("La senal esta casi siempre long; tal vez se parece demasiado a buy and hold.")
    if rows < 252:
        st.warning("Poco historial para evaluar senales con confianza.")


def price_overlay_columns(frame: pd.DataFrame) -> tuple[str, ...]:
    prefixes = ("sma_", "rolling_high_", "rolling_low_")
    columns = [
        column
        for column in frame.columns
        if column.startswith(prefixes) and pd.api.types.is_numeric_dtype(frame[column])
    ]
    return tuple(columns[:5])
