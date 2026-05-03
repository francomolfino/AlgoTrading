from __future__ import annotations

from dataclasses import replace

from algotrading.paper_trading.models import Bar, Fill, Order, OrderSide, OrderStatus


class FakeBroker:
    """Broker fake con ejecucion inmediata de market orders sobre la barra actual."""

    def __init__(
        self,
        initial_cash: float = 10_000.0,
        commission_bps: float = 1.0,
        slippage_bps: float = 2.0,
    ):
        if initial_cash <= 0:
            raise ValueError("initial_cash debe ser mayor a cero.")
        if commission_bps < 0:
            raise ValueError("commission_bps no puede ser negativo.")
        if slippage_bps < 0:
            raise ValueError("slippage_bps no puede ser negativo.")

        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.commission_bps = float(commission_bps)
        self.slippage_bps = float(slippage_bps)
        self.positions: dict[str, float] = {}
        self.orders: list[Order] = []
        self.fills: list[Fill] = []

    def get_position(self, symbol: str) -> float:
        return float(self.positions.get(symbol, 0.0))

    def equity(self, mark_prices: dict[str, float]) -> float:
        position_value = sum(
            quantity * mark_prices.get(symbol, 0.0)
            for symbol, quantity in self.positions.items()
        )
        return self.cash + position_value

    def submit_market_order(
        self,
        order: Order,
        bar: Bar,
        price_column: str = "adj_close",
    ) -> Fill | None:
        if order.quantity <= 0:
            rejected = replace(order, status=OrderStatus.REJECTED, reason="quantity <= 0")
            self.orders.append(rejected)
            return None

        price = bar.price(price_column)
        if order.side == OrderSide.BUY:
            return self._buy(order, price)
        if order.side == OrderSide.SELL:
            return self._sell(order, price)
        raise ValueError(f"Side no soportado: {order.side}")

    def _buy(self, order: Order, mark_price: float) -> Fill | None:
        execution_price = mark_price * (1 + self.slippage_bps / 10_000)
        commission_rate = self.commission_bps / 10_000
        max_affordable_quantity = self.cash / (execution_price * (1 + commission_rate))
        quantity = min(order.quantity, max_affordable_quantity)
        if quantity <= 0:
            rejected = replace(order, status=OrderStatus.REJECTED, reason="insufficient cash")
            self.orders.append(rejected)
            return None

        notional = quantity * execution_price
        commission = notional * commission_rate
        self.cash -= notional + commission
        self.positions[order.symbol] = self.get_position(order.symbol) + quantity

        filled = replace(order, quantity=quantity, status=OrderStatus.FILLED)
        fill = Fill(
            order_id=filled.order_id,
            timestamp=filled.timestamp,
            symbol=filled.symbol,
            side=filled.side,
            quantity=quantity,
            price=execution_price,
            notional=notional,
            commission=commission,
            slippage_bps=self.slippage_bps,
        )
        self.orders.append(filled)
        self.fills.append(fill)
        return fill

    def _sell(self, order: Order, mark_price: float) -> Fill | None:
        current_quantity = self.get_position(order.symbol)
        quantity = min(order.quantity, current_quantity)
        if quantity <= 0:
            rejected = replace(order, status=OrderStatus.REJECTED, reason="no position")
            self.orders.append(rejected)
            return None

        execution_price = mark_price * (1 - self.slippage_bps / 10_000)
        notional = quantity * execution_price
        commission = notional * (self.commission_bps / 10_000)
        self.cash += notional - commission
        remaining = current_quantity - quantity
        if remaining <= 1e-12:
            self.positions.pop(order.symbol, None)
        else:
            self.positions[order.symbol] = remaining

        filled = replace(order, quantity=quantity, status=OrderStatus.FILLED)
        fill = Fill(
            order_id=filled.order_id,
            timestamp=filled.timestamp,
            symbol=filled.symbol,
            side=filled.side,
            quantity=quantity,
            price=execution_price,
            notional=notional,
            commission=commission,
            slippage_bps=self.slippage_bps,
        )
        self.orders.append(filled)
        self.fills.append(fill)
        return fill
