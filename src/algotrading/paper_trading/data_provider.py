from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

import pandas as pd

from algotrading.data.schema import normalize_ohlcv_dataframe
from algotrading.data.yahoo import download_ohlcv
from algotrading.paper_trading.models import Bar, MarketEvent, MarketEventType


@runtime_checkable
class MarketDataProvider(Protocol):
    """Contrato minimo para engines que consumen barras."""

    symbol: str

    def iter_bars(self) -> Iterator[Bar]:
        """Emite barras OHLCV en orden cronologico."""


@runtime_checkable
class MarketEventProvider(Protocol):
    """Contrato minimo para loops live/replay basados en eventos."""

    symbol: str

    def iter_events(self) -> Iterator[MarketEvent]:
        """Emite eventos de mercado en orden cronologico."""


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

    def iter_events(self) -> Iterator[MarketEvent]:
        for bar in self.iter_bars():
            yield MarketEvent.from_bar(bar)


class YahooHistoricalDataProvider(HistoricalDataProvider):
    """Provider historico basado en yfinance.

    Mantiene a yfinance encapsulado para que despues podamos cambiar la fuente
    sin tocar estrategias ni motores.
    """

    def __init__(
        self,
        symbol: str,
        start: str,
        end: str | None = None,
        interval: str = "1d",
    ):
        frame = download_ohlcv(symbol=symbol, start=start, end=end, interval=interval)
        super().__init__(symbol=symbol, frame=frame)


class FakeLiveDataProvider(HistoricalDataProvider):
    """Replay historico con forma de provider live para pruebas locales."""

    def __init__(
        self,
        symbol: str,
        frame: pd.DataFrame,
        heartbeat_every: int | None = None,
        emit_market_closed: bool = True,
    ):
        if heartbeat_every is not None and heartbeat_every <= 0:
            raise ValueError("heartbeat_every debe ser positivo o None.")
        super().__init__(symbol=symbol, frame=frame)
        self.heartbeat_every = heartbeat_every
        self.emit_market_closed = bool(emit_market_closed)

    def iter_events(self) -> Iterator[MarketEvent]:
        last_timestamp: pd.Timestamp | None = None
        for index, bar in enumerate(self.iter_bars(), start=1):
            last_timestamp = bar.date
            yield MarketEvent.from_bar(bar)
            if self.heartbeat_every is not None and index % self.heartbeat_every == 0:
                yield MarketEvent(
                    timestamp=bar.date,
                    event_type=MarketEventType.HEARTBEAT,
                    symbol=self.symbol,
                    message=f"heartbeat after {index} bars",
                )

        if self.emit_market_closed and last_timestamp is not None:
            yield MarketEvent(
                timestamp=last_timestamp,
                event_type=MarketEventType.MARKET_CLOSED,
                symbol=self.symbol,
                message="historical replay finished",
            )


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return normalize_ohlcv_dataframe(frame)
