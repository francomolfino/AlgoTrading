from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import pandas as pd

from algotrading.paper_trading.models import (
    Bar,
    BrokerError,
    Fill,
    Order,
    OrderEvent,
    OrderSide,
    OrderStatus,
)


class FakeBroker:
    """Broker fake con lifecycle auditable y ejecucion inmediata de market orders."""

    def __init__(
        self,
        initial_cash: float = 10_000.0,
        commission_bps: float = 1.0,
        slippage_bps: float = 2.0,
        dry_run: bool = False,
        auto_persist_path: Path | str | None = None,
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
        self.dry_run = bool(dry_run)
        self.auto_persist_path = Path(auto_persist_path) if auto_persist_path else None
        self.positions: dict[str, float] = {}
        self.orders: list[Order] = []
        self.fills: list[Fill] = []
        self.order_events: list[OrderEvent] = []
        self.error_events: list[BrokerError] = []

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
        created = replace(order, status=OrderStatus.CREATED, reason="")
        self._record_event(created, OrderStatus.CREATED, "order created")
        submitted = replace(created, status=OrderStatus.SUBMITTED)
        self._record_event(submitted, OrderStatus.SUBMITTED, "order submitted")

        try:
            if submitted.quantity <= 0:
                return self._reject(submitted, "quantity <= 0")

            price = bar.price(price_column)
            if self.dry_run:
                cancelled = replace(submitted, status=OrderStatus.CANCELLED, reason="dry_run")
                self.orders.append(cancelled)
                self._record_event(cancelled, OrderStatus.CANCELLED, "dry-run mode: order not filled")
                self._auto_persist()
                return None

            if submitted.side == OrderSide.BUY:
                fill = self._buy(submitted, price)
            elif submitted.side == OrderSide.SELL:
                fill = self._sell(submitted, price)
            else:
                fill = self._reject(submitted, f"Side no soportado: {submitted.side}")
            self._auto_persist()
            return fill
        except Exception as exc:
            self._record_error(submitted, type(exc).__name__, str(exc))
            self._auto_persist()
            raise

    def cancel_order(self, order: Order, reason: str = "cancelled") -> Order:
        cancelled = replace(order, status=OrderStatus.CANCELLED, reason=reason)
        self.orders.append(cancelled)
        self._record_event(cancelled, OrderStatus.CANCELLED, reason)
        self._auto_persist()
        return cancelled

    def save_state(self, path: Path | str) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_state(), indent=2), encoding="utf-8")
        return output_path

    @classmethod
    def load_state(cls, path: Path | str) -> FakeBroker:
        input_path = Path(path)
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        broker = cls(
            initial_cash=float(payload["initial_cash"]),
            commission_bps=float(payload["commission_bps"]),
            slippage_bps=float(payload["slippage_bps"]),
            dry_run=bool(payload.get("dry_run", False)),
        )
        broker.cash = float(payload["cash"])
        broker.positions = {symbol: float(quantity) for symbol, quantity in payload["positions"].items()}
        broker.orders = [_order_from_record(record) for record in payload.get("orders", [])]
        broker.fills = [_fill_from_record(record) for record in payload.get("fills", [])]
        broker.order_events = [
            _order_event_from_record(record) for record in payload.get("order_events", [])
        ]
        broker.error_events = [
            _broker_error_from_record(record) for record in payload.get("error_events", [])
        ]
        return broker

    def to_state(self) -> dict[str, Any]:
        return {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "dry_run": self.dry_run,
            "positions": self.positions,
            "orders": [_order_record(order) for order in self.orders],
            "fills": [_fill_record(fill) for fill in self.fills],
            "order_events": [_order_event_record(event) for event in self.order_events],
            "error_events": [_broker_error_record(error) for error in self.error_events],
        }

    def _buy(self, order: Order, mark_price: float) -> Fill | None:
        execution_price = mark_price * (1 + self.slippage_bps / 10_000)
        commission_rate = self.commission_bps / 10_000
        max_affordable_quantity = self.cash / (execution_price * (1 + commission_rate))
        quantity = min(order.quantity, max_affordable_quantity)
        if quantity <= 0:
            return self._reject(order, "insufficient cash")

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
        self._record_event(filled, OrderStatus.FILLED, "order filled")
        return fill

    def _sell(self, order: Order, mark_price: float) -> Fill | None:
        current_quantity = self.get_position(order.symbol)
        quantity = min(order.quantity, current_quantity)
        if quantity <= 0:
            return self._reject(order, "no position")

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
        self._record_event(filled, OrderStatus.FILLED, "order filled")
        return fill

    def _reject(self, order: Order, reason: str) -> None:
        rejected = replace(order, status=OrderStatus.REJECTED, reason=reason)
        self.orders.append(rejected)
        self._record_event(rejected, OrderStatus.REJECTED, reason)
        self._record_error(rejected, "OrderRejected", reason)
        self._auto_persist()
        return None

    def _record_event(self, order: Order, status: OrderStatus, message: str) -> None:
        self.order_events.append(
            OrderEvent(
                order_id=order.order_id,
                timestamp=order.timestamp,
                symbol=order.symbol,
                status=status,
                message=message,
            )
        )

    def _record_error(self, order: Order, error_type: str, message: str) -> None:
        self.error_events.append(
            BrokerError(
                timestamp=order.timestamp,
                order_id=order.order_id,
                symbol=order.symbol,
                error_type=error_type,
                message=message,
            )
        )

    def _auto_persist(self) -> None:
        if self.auto_persist_path is not None:
            self.save_state(self.auto_persist_path)


def _order_record(order: Order) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "timestamp": order.timestamp.isoformat(),
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": order.quantity,
        "status": order.status.value,
        "reason": order.reason,
    }


def _fill_record(fill: Fill) -> dict[str, Any]:
    return {
        "order_id": fill.order_id,
        "timestamp": fill.timestamp.isoformat(),
        "symbol": fill.symbol,
        "side": fill.side.value,
        "quantity": fill.quantity,
        "price": fill.price,
        "notional": fill.notional,
        "commission": fill.commission,
        "slippage_bps": fill.slippage_bps,
    }


def _order_event_record(event: OrderEvent) -> dict[str, Any]:
    return {
        "order_id": event.order_id,
        "timestamp": event.timestamp.isoformat(),
        "symbol": event.symbol,
        "status": event.status.value,
        "message": event.message,
    }


def _broker_error_record(error: BrokerError) -> dict[str, Any]:
    return {
        "timestamp": error.timestamp.isoformat(),
        "order_id": error.order_id,
        "symbol": error.symbol,
        "error_type": error.error_type,
        "message": error.message,
    }


def _order_from_record(record: dict[str, Any]) -> Order:
    return Order(
        order_id=int(record["order_id"]),
        timestamp=pd.Timestamp(record["timestamp"]),
        symbol=str(record["symbol"]),
        side=OrderSide(record["side"]),
        quantity=float(record["quantity"]),
        status=OrderStatus(record["status"]),
        reason=str(record.get("reason", "")),
    )


def _fill_from_record(record: dict[str, Any]) -> Fill:
    return Fill(
        order_id=int(record["order_id"]),
        timestamp=pd.Timestamp(record["timestamp"]),
        symbol=str(record["symbol"]),
        side=OrderSide(record["side"]),
        quantity=float(record["quantity"]),
        price=float(record["price"]),
        notional=float(record["notional"]),
        commission=float(record["commission"]),
        slippage_bps=float(record["slippage_bps"]),
    )


def _order_event_from_record(record: dict[str, Any]) -> OrderEvent:
    return OrderEvent(
        order_id=int(record["order_id"]),
        timestamp=pd.Timestamp(record["timestamp"]),
        symbol=str(record["symbol"]),
        status=OrderStatus(record["status"]),
        message=str(record.get("message", "")),
    )


def _broker_error_from_record(record: dict[str, Any]) -> BrokerError:
    return BrokerError(
        timestamp=pd.Timestamp(record["timestamp"]),
        order_id=int(record["order_id"]),
        symbol=str(record["symbol"]),
        error_type=str(record["error_type"]),
        message=str(record["message"]),
    )
