from __future__ import annotations

import pandas as pd
import yfinance as yf

from algotrading.data.schema import ValidationError, normalize_ohlcv_dataframe


def download_ohlcv(
    symbol: str,
    start: str,
    end: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Descarga un simbolo desde Yahoo Finance y devuelve OHLCV normalizado."""
    raw = yf.download(
        tickers=symbol,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=False,
    )

    if raw.empty:
        raise ValidationError(
            f"Yahoo Finance no devolvio datos para {symbol}. Revisa ticker, fechas o conexion."
        )

    raw = _select_symbol_from_yfinance_frame(raw, symbol)
    return normalize_ohlcv_dataframe(raw)


def _select_symbol_from_yfinance_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame

    levels = frame.columns.names
    for level_index in range(frame.columns.nlevels):
        level_values = frame.columns.get_level_values(level_index)
        if symbol in set(level_values):
            return frame.xs(symbol, axis=1, level=level_index)

    # Fallback defensivo: si yfinance devuelve MultiIndex sin el ticker esperado,
    # asumimos que el primer nivel contiene los nombres de precio.
    if "Price" in levels:
        return frame.droplevel([i for i, name in enumerate(levels) if name != "Price"], axis=1)

    raise ValidationError(f"No se pudo interpretar la respuesta MultiIndex para {symbol}.")
