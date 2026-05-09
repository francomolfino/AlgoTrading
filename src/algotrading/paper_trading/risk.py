from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from algotrading.paper_trading.models import Order, OrderSide
from algotrading.risk import RiskLimitState, can_submit_order, cap_fraction, update_trade_count


@dataclass(frozen=True)
class RiskManagerConfig:
    max_position_fraction: float = 1.0
    max_total_exposure: float = 1.0
    max_drawdown_pct: float | None = None
    max_trades_per_day: int | None = None
    min_trade_value: float = 25.0
    allow_fractional: bool = True


class RiskManager:
    """Convierte pesos objetivo en ordenes, aplicando reglas simples de riesgo."""

    def __init__(self, config: RiskManagerConfig | None = None):
        self.config = config or RiskManagerConfig()
        if not 0 <= self.config.max_position_fraction <= 1:
            raise ValueError("max_position_fraction debe estar entre 0 y 1.")
        if not 0 <= self.config.max_total_exposure <= 1:
            raise ValueError("max_total_exposure debe estar entre 0 y 1.")
        if self.config.max_drawdown_pct is not None and not 0 < self.config.max_drawdown_pct < 1:
            raise ValueError("max_drawdown_pct debe estar entre 0 y 1.")
        if self.config.max_trades_per_day is not None and self.config.max_trades_per_day < 0:
            raise ValueError("max_trades_per_day no puede ser negativo.")
        if self.config.min_trade_value < 0:
            raise ValueError("min_trade_value no puede ser negativo.")
        self._risk_state: RiskLimitState | None = None
        self._trade_counts: dict[pd.Timestamp, int] = {}
        self.last_risk_event = ""
        self.last_blocked_reason = ""

    def create_order_for_target_weight(
        self,
        order_id: int,
        timestamp: pd.Timestamp,
        symbol: str,
        target_weight: float,
        current_quantity: float,
        price: float,
        equity: float,
    ) -> Order | None:
        if price <= 0:
            raise ValueError("price debe ser mayor a cero.")
        if equity <= 0:
            raise ValueError("equity debe ser mayor a cero.")
        if target_weight < 0:
            raise ValueError("Este risk manager no permite posiciones short.")

        self.last_risk_event = ""
        self.last_blocked_reason = ""
        self._update_risk_state(equity)

        if self._risk_state and self._risk_state.halted:
            target_weight = 0.0
            self.last_risk_event = self._risk_state.halt_reason

        capped_target = cap_fraction(
            target_weight,
            min(self.config.max_position_fraction, self.config.max_total_exposure),
        )
        current_value = current_quantity * price
        target_value = capped_target * equity
        delta_value = target_value - current_value
        if abs(delta_value) < self.config.min_trade_value:
            return None

        if not can_submit_order(timestamp, self._trade_counts, self.config.max_trades_per_day):
            self.last_blocked_reason = "trade_limit"
            return None

        side = OrderSide.BUY if delta_value > 0 else OrderSide.SELL
        quantity = abs(delta_value) / price
        if not self.config.allow_fractional:
            quantity = float(int(quantity))
        if quantity <= 0:
            return None

        update_trade_count(timestamp, self._trade_counts)

        return Order(
            order_id=order_id,
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            quantity=quantity,
        )

    def _update_risk_state(self, equity: float) -> None:
        if self._risk_state is None:
            self._risk_state = RiskLimitState(equity_peak=float(equity))
        self._risk_state.update_peak(equity)
        if self._risk_state.check_max_drawdown(equity, self.config.max_drawdown_pct):
            self.last_risk_event = self._risk_state.halt_reason
