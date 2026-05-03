from __future__ import annotations

from typing import Protocol

import pandas as pd


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
