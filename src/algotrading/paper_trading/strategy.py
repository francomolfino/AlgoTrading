from __future__ import annotations

from typing import Protocol

import pandas as pd

from algotrading.strategies.breakout import generate_breakout_signals
from algotrading.strategies.rsi import generate_rsi_signals
from algotrading.strategies.trend_filter import generate_trend_filter_signals


class PaperStrategy(Protocol):
    name: str

    def target_weight(self, history: pd.DataFrame) -> float:
        """Devuelve peso objetivo long-only entre 0 y 1."""


class BuyAndHoldPaperStrategy:
    name = "buy_and_hold"

    def target_weight(self, history: pd.DataFrame) -> float:
        return 1.0 if len(history) > 0 else 0.0


class MovingAverageCrossoverPaperStrategy:
    def __init__(
        self,
        fast_window: int = 20,
        slow_window: int = 200,
        price_column: str = "adj_close",
    ):
        if fast_window <= 0 or slow_window <= 0:
            raise ValueError("Las ventanas deben ser positivas.")
        if fast_window >= slow_window:
            raise ValueError("fast_window debe ser menor que slow_window.")
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.price_column = price_column
        self.name = f"sma_cross_{fast_window}_{slow_window}"

    def target_weight(self, history: pd.DataFrame) -> float:
        if self.price_column not in history.columns:
            raise ValueError(f"Falta columna de precio: {self.price_column}")
        if len(history) < self.slow_window:
            return 0.0

        prices = pd.to_numeric(history[self.price_column], errors="coerce")
        fast = prices.rolling(self.fast_window).mean().iloc[-1]
        slow = prices.rolling(self.slow_window).mean().iloc[-1]
        return 1.0 if fast > slow else 0.0


class RSIPaperStrategy:
    def __init__(
        self,
        window: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        price_column: str = "adj_close",
    ):
        if window <= 0:
            raise ValueError("window debe ser positivo.")
        if not 0 <= oversold < overbought <= 100:
            raise ValueError("Se requiere 0 <= oversold < overbought <= 100.")
        self.window = int(window)
        self.oversold = float(oversold)
        self.overbought = float(overbought)
        self.price_column = price_column
        self.name = f"rsi_{self.window}_{self.oversold:g}_{self.overbought:g}"

    def target_weight(self, history: pd.DataFrame) -> float:
        signal_frame = _latest_signal_frame(
            history,
            minimum_rows=self.window + 1,
            generator=generate_rsi_signals,
            window=self.window,
            oversold=self.oversold,
            overbought=self.overbought,
            price_column=self.price_column,
        )
        return _latest_target(signal_frame)


class BreakoutPaperStrategy:
    def __init__(
        self,
        entry_window: int = 55,
        exit_window: int = 20,
        price_column: str = "adj_close",
    ):
        if entry_window <= 0 or exit_window <= 0:
            raise ValueError("Las ventanas deben ser positivas.")
        self.entry_window = int(entry_window)
        self.exit_window = int(exit_window)
        self.price_column = price_column
        self.name = f"breakout_{self.entry_window}_{self.exit_window}"

    def target_weight(self, history: pd.DataFrame) -> float:
        signal_frame = _latest_signal_frame(
            history,
            minimum_rows=max(self.entry_window, self.exit_window) + 1,
            generator=generate_breakout_signals,
            entry_window=self.entry_window,
            exit_window=self.exit_window,
            price_column=self.price_column,
        )
        return _latest_target(signal_frame)


class TrendFilterPaperStrategy:
    def __init__(
        self,
        fast_window: int = 20,
        slow_window: int = 100,
        trend_window: int = 200,
        price_column: str = "adj_close",
    ):
        if fast_window <= 0 or slow_window <= 0 or trend_window <= 0:
            raise ValueError("Las ventanas deben ser positivas.")
        if fast_window >= slow_window:
            raise ValueError("fast_window debe ser menor que slow_window.")
        self.fast_window = int(fast_window)
        self.slow_window = int(slow_window)
        self.trend_window = int(trend_window)
        self.price_column = price_column
        self.name = f"trend_filter_{self.fast_window}_{self.slow_window}_{self.trend_window}"

    def target_weight(self, history: pd.DataFrame) -> float:
        signal_frame = _latest_signal_frame(
            history,
            minimum_rows=max(self.fast_window, self.slow_window, self.trend_window),
            generator=generate_trend_filter_signals,
            fast_window=self.fast_window,
            slow_window=self.slow_window,
            trend_window=self.trend_window,
            price_column=self.price_column,
        )
        return _latest_target(signal_frame)


def _latest_signal_frame(
    history: pd.DataFrame,
    minimum_rows: int,
    generator,
    **kwargs,
) -> pd.DataFrame:
    if len(history) < minimum_rows:
        return pd.DataFrame()
    return generator(history, signal_column="signal", **kwargs)


def _latest_target(signal_frame: pd.DataFrame) -> float:
    if signal_frame.empty or "signal" not in signal_frame.columns:
        return 0.0
    signal = pd.to_numeric(signal_frame["signal"], errors="coerce").fillna(0)
    return 1.0 if int(signal.iloc[-1]) == 1 else 0.0
