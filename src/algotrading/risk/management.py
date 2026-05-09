from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd


@dataclass
class RiskLimitState:
    """Estado minimo para reglas que dependen del historial."""

    equity_peak: float
    halted: bool = False
    halt_reason: str = ""

    def update_peak(self, equity: float) -> None:
        self.equity_peak = max(self.equity_peak, float(equity))

    def drawdown(self, equity: float) -> float:
        return calculate_drawdown_fraction(equity=equity, peak=self.equity_peak)

    def check_max_drawdown(self, equity: float, max_drawdown_pct: float | None) -> bool:
        if max_drawdown_pct is None or self.halted:
            return False
        if self.drawdown(equity) <= -max_drawdown_pct:
            self.halted = True
            self.halt_reason = "max_drawdown"
            return True
        return False


def cap_fraction(value: float, maximum: float) -> float:
    """Limita una fraccion long-only al rango [0, maximum]."""
    if maximum < 0:
        raise ValueError("maximum no puede ser negativo.")
    return max(0.0, min(float(value), float(maximum)))


def calculate_drawdown_fraction(equity: float, peak: float) -> float:
    if peak <= 0:
        raise ValueError("peak debe ser mayor a cero.")
    return float(equity / peak - 1)


def calculate_volatility_target_fraction(
    prices: pd.Series,
    index: int,
    base_fraction: float,
    target_volatility: float | None,
    window: int = 20,
    periods_per_year: int = 252,
) -> float:
    """Reduce exposicion si la volatilidad realizada supera el objetivo.

    Usa solo precios anteriores al indice de ejecucion para evitar lookahead.
    """
    if target_volatility is None:
        return float(base_fraction)
    if target_volatility <= 0:
        raise ValueError("target_volatility debe ser mayor a cero.")
    if window <= 1:
        raise ValueError("window debe ser mayor a uno.")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor a cero.")

    history = pd.to_numeric(prices.iloc[:index], errors="coerce").dropna()
    if len(history) <= window:
        return float(base_fraction)

    returns = history.pct_change(fill_method=None).dropna().tail(window)
    realized_volatility = float(returns.std(ddof=0) * math.sqrt(periods_per_year))
    if realized_volatility <= 0 or math.isnan(realized_volatility):
        return float(base_fraction)
    return cap_fraction(base_fraction * target_volatility / realized_volatility, base_fraction)


def can_submit_order(
    timestamp: pd.Timestamp,
    trade_counts: dict[pd.Timestamp, int],
    max_trades_per_day: int | None,
) -> bool:
    if max_trades_per_day is None:
        return True
    if max_trades_per_day < 0:
        raise ValueError("max_trades_per_day no puede ser negativo.")
    day = pd.Timestamp(timestamp).normalize()
    return trade_counts.get(day, 0) < max_trades_per_day


def update_trade_count(timestamp: pd.Timestamp, trade_counts: dict[pd.Timestamp, int]) -> None:
    day = pd.Timestamp(timestamp).normalize()
    trade_counts[day] = trade_counts.get(day, 0) + 1
