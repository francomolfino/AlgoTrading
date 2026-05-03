from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from algotrading.paper_trading.models import Order, OrderSide


@dataclass(frozen=True)
class RiskManagerConfig:
    max_position_fraction: float = 1.0
    min_trade_value: float = 25.0
    allow_fractional: bool = True


class RiskManager:
    """Convierte pesos objetivo en ordenes, aplicando reglas simples de riesgo."""

    def __init__(self, config: RiskManagerConfig | None = None):
        self.config = config or RiskManagerConfig()
        if not 0 <= self.config.max_position_fraction <= 1:
            raise ValueError("max_position_fraction debe estar entre 0 y 1.")
        if self.config.min_trade_value < 0:
            raise ValueError("min_trade_value no puede ser negativo.")

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

        capped_target = min(target_weight, self.config.max_position_fraction)
        current_value = current_quantity * price
        target_value = capped_target * equity
        delta_value = target_value - current_value
        if abs(delta_value) < self.config.min_trade_value:
            return None

        side = OrderSide.BUY if delta_value > 0 else OrderSide.SELL
        quantity = abs(delta_value) / price
        if not self.config.allow_fractional:
            quantity = float(int(quantity))
        if quantity <= 0:
            return None

        return Order(
            order_id=order_id,
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            quantity=quantity,
        )
