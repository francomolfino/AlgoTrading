from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from algotrading.metrics import calculate_drawdown, calculate_total_return
from algotrading.paper_trading.broker import FakeBroker
from algotrading.paper_trading.data_provider import MarketDataProvider
from algotrading.paper_trading.risk import RiskManager
from algotrading.paper_trading.strategy import PaperStrategy


@dataclass(frozen=True)
class PaperTradingResult:
    account_history: pd.DataFrame
    orders: pd.DataFrame
    order_events: pd.DataFrame
    fills: pd.DataFrame
    errors: pd.DataFrame
    summary: dict[str, float | int | str]


class PaperTradingEngine:
    """Motor educativo que simula paper trading barra por barra."""

    def __init__(
        self,
        data_provider: MarketDataProvider,
        strategy: PaperStrategy,
        broker: FakeBroker,
        risk_manager: RiskManager,
        price_column: str = "adj_close",
    ):
        self.data_provider = data_provider
        self.strategy = strategy
        self.broker = broker
        self.risk_manager = risk_manager
        self.price_column = price_column

    def run(self) -> PaperTradingResult:
        history_records: list[dict[str, float | str | pd.Timestamp]] = []
        account_rows: list[dict[str, float | int | str | pd.Timestamp]] = []
        next_order_id = 1
        pending_target_weight = 0.0

        for bar in self.data_provider.iter_bars():
            price = bar.price(self.price_column)
            fill = None
            action = ""
            equity_before = self.broker.equity({bar.symbol: price})
            order = self.risk_manager.create_order_for_target_weight(
                order_id=next_order_id,
                timestamp=bar.date,
                symbol=bar.symbol,
                target_weight=pending_target_weight,
                current_quantity=self.broker.get_position(bar.symbol),
                price=price,
                equity=equity_before,
            )
            if order is not None:
                next_order_id += 1
                fill = self.broker.submit_market_order(order, bar, price_column=self.price_column)
                action = fill.side.value if fill else _last_order_action(self.broker.orders)

            history_records.append(bar.to_record())
            history = pd.DataFrame(history_records)
            next_target_weight = self.strategy.target_weight(history)
            equity = self.broker.equity({bar.symbol: price})
            account_rows.append(
                {
                    "date": bar.date,
                    "symbol": bar.symbol,
                    "price": price,
                    "executed_target_weight": pending_target_weight,
                    "next_target_weight": next_target_weight,
                    "position_quantity": self.broker.get_position(bar.symbol),
                    "cash": self.broker.cash,
                    "equity": equity,
                    "action": action,
                    "risk_event": self.risk_manager.last_risk_event,
                    "blocked_reason": self.risk_manager.last_blocked_reason,
                    "fill_price": fill.price if fill else math.nan,
                    "fill_quantity": fill.quantity if fill else 0.0,
                    "commission": fill.commission if fill else 0.0,
                }
            )
            pending_target_weight = next_target_weight

        account_history = pd.DataFrame(account_rows)
        if account_history.empty:
            raise ValueError("No se recibieron barras del data provider.")
        account_history["daily_return"] = account_history["equity"].pct_change(fill_method=None).fillna(0.0)
        account_history["equity_peak"] = account_history["equity"].cummax()
        account_history["drawdown"] = calculate_drawdown(account_history["equity"])

        orders = _orders_frame(self.broker.orders)
        order_events = _order_events_frame(self.broker.order_events)
        fills = _fills_frame(self.broker.fills)
        errors = _errors_frame(self.broker.error_events)
        summary = _summary(
            account_history=account_history,
            orders=orders,
            order_events=order_events,
            fills=fills,
            errors=errors,
            initial_cash=self.broker.initial_cash,
            strategy_name=self.strategy.name,
            dry_run=self.broker.dry_run,
        )
        return PaperTradingResult(
            account_history=account_history,
            orders=orders,
            order_events=order_events,
            fills=fills,
            errors=errors,
            summary=summary,
        )


def _orders_frame(orders) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "order_id": order.order_id,
                "timestamp": order.timestamp,
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "status": order.status.value,
                "reason": order.reason,
            }
            for order in orders
        ],
        columns=["order_id", "timestamp", "symbol", "side", "quantity", "status", "reason"],
    )


def _fills_frame(fills) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "order_id": fill.order_id,
                "timestamp": fill.timestamp,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": fill.price,
                "notional": fill.notional,
                "commission": fill.commission,
                "slippage_bps": fill.slippage_bps,
            }
            for fill in fills
        ],
        columns=[
            "order_id",
            "timestamp",
            "symbol",
            "side",
            "quantity",
            "price",
            "notional",
            "commission",
            "slippage_bps",
        ],
    )


def _order_events_frame(events) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "order_id": event.order_id,
                "timestamp": event.timestamp,
                "symbol": event.symbol,
                "status": event.status.value,
                "message": event.message,
            }
            for event in events
        ],
        columns=["order_id", "timestamp", "symbol", "status", "message"],
    )


def _errors_frame(errors) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": error.timestamp,
                "order_id": error.order_id,
                "symbol": error.symbol,
                "error_type": error.error_type,
                "message": error.message,
            }
            for error in errors
        ],
        columns=["timestamp", "order_id", "symbol", "error_type", "message"],
    )


def _summary(
    account_history: pd.DataFrame,
    orders: pd.DataFrame,
    order_events: pd.DataFrame,
    fills: pd.DataFrame,
    errors: pd.DataFrame,
    initial_cash: float,
    strategy_name: str,
    dry_run: bool,
) -> dict[str, float | int | str]:
    final_equity = float(account_history["equity"].iloc[-1])
    total_return = calculate_total_return(initial_cash, final_equity)
    return {
        "strategy": strategy_name,
        "start_date": account_history["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": account_history["date"].iloc[-1].strftime("%Y-%m-%d"),
        "initial_cash": float(initial_cash),
        "final_equity": final_equity,
        "total_return": float(total_return),
        "max_drawdown": float(account_history["drawdown"].min()),
        "orders": int(len(orders)),
        "order_events": int(len(order_events)),
        "fills": int(len(fills)),
        "errors": int(len(errors)),
        "dry_run": int(dry_run),
        "total_commissions": float(fills["commission"].sum()) if len(fills) else 0.0,
        "final_cash": float(account_history["cash"].iloc[-1]),
        "final_position_quantity": float(account_history["position_quantity"].iloc[-1]),
        "risk_halt_triggered": int((account_history["risk_event"] == "max_drawdown").any())
        if "risk_event" in account_history.columns
        else 0,
    }


def _last_order_action(orders) -> str:
    if not orders:
        return "rejected"
    status = orders[-1].status.value
    return "dry_run" if status == "cancelled" and orders[-1].reason == "dry_run" else status
