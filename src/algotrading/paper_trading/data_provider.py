from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from algotrading.paper_trading.models import Bar


class HistoricalDataProvider:
    """Data provider historico que emite barras una por una."""

    def __init__(self, symbol: str, frame: pd.DataFrame):
        self.symbol = symbol
        self.frame = _prepare_frame(frame)

    def iter_bars(self) -> Iterator[Bar]:
        for row in self.frame.itertuples(index=False):
            yield Bar(
                date=row.date,
                symbol=self.symbol,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                adj_close=float(row.adj_close),
                volume=float(row.volume),
            )


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    data = frame[required_columns].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for column in required_columns:
        if column != "date":
            data[column] = pd.to_numeric(data[column], errors="coerce")

    if data.isna().any().any():
        raise ValueError("Hay valores invalidos en los datos historicos.")
    return data.sort_values("date").reset_index(drop=True)
