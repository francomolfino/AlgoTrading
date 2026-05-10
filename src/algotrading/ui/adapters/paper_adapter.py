from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from algotrading.paper_trading import (
    BreakoutPaperStrategy,
    BuyAndHoldPaperStrategy,
    FakeBroker,
    HistoricalDataProvider,
    MovingAverageCrossoverPaperStrategy,
    PaperTradingEngine,
    PaperTradingResult,
    RSIPaperStrategy,
    RiskManager,
    RiskManagerConfig,
    TrendFilterPaperStrategy,
)
from algotrading.ui.adapters.data_adapter import filter_by_dates, load_symbol_data


@dataclass(frozen=True)
class PaperTradingRequest:
    symbol: str
    strategy_key: str
    strategy_parameters: dict[str, int | float]
    data_dir: Path | str = "data/raw"
    interval: str = "1d"
    start: str | None = None
    end: str | None = None
    price_column: str = "adj_close"
    initial_cash: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    max_position_fraction: float = 1.0
    max_total_exposure: float = 1.0
    max_drawdown_pct: float | None = None
    max_trades_per_day: int | None = None
    min_trade_value: float = 25.0
    dry_run: bool = False


def run_paper_trading_request(request: PaperTradingRequest) -> PaperTradingResult:
    if request.initial_cash <= 0:
        raise ValueError("El capital simulado debe ser mayor a cero.")
    frame, _ = load_symbol_data(request.data_dir, request.symbol, request.interval)
    frame = filter_by_dates(frame, request.start, request.end)
    provider = HistoricalDataProvider(request.symbol, frame)
    broker = FakeBroker(
        initial_cash=request.initial_cash,
        commission_bps=request.commission_bps,
        slippage_bps=request.slippage_bps,
        dry_run=request.dry_run,
    )
    risk = RiskManager(
        RiskManagerConfig(
            max_position_fraction=request.max_position_fraction,
            max_total_exposure=request.max_total_exposure,
            max_drawdown_pct=request.max_drawdown_pct,
            max_trades_per_day=request.max_trades_per_day,
            min_trade_value=request.min_trade_value,
        )
    )
    engine = PaperTradingEngine(
        data_provider=provider,
        strategy=_paper_strategy(request),
        broker=broker,
        risk_manager=risk,
        price_column=request.price_column,
    )
    return engine.run()


def supported_paper_strategies() -> dict[str, str]:
    return {
        "buy_and_hold": "Buy and hold",
        "sma_cross": "Cruce de medias moviles",
        "rsi": "RSI basico",
        "breakout": "Breakout simple",
        "trend_filter": "Cruce con filtro de tendencia",
    }


def build_paper_replay_frame(result: PaperTradingResult) -> pd.DataFrame:
    """Arma un timeline auditable de la simulacion paper barra por barra."""
    account = result.account_history.copy()
    if account.empty:
        return pd.DataFrame()
    account["date"] = pd.to_datetime(account["date"], errors="coerce")
    events = _events_by_timestamp(result.order_events)
    orders = _orders_by_timestamp(result.orders)
    fills = _fills_by_timestamp(result.fills)
    rows = []
    for index, row in account.reset_index(drop=True).iterrows():
        timestamp = row["date"]
        key = _timestamp_key(timestamp)
        price = _to_float(row.get("price"))
        equity = _to_float(row.get("equity"))
        cash = _to_float(row.get("cash"))
        position_quantity = _to_float(row.get("position_quantity"))
        executed_target_weight = _to_float(row.get("executed_target_weight"))
        next_target_weight = _to_float(row.get("next_target_weight"))
        current_position_value = position_quantity * price
        current_weight = current_position_value / equity if equity > 0 else 0.0
        action = _clean_text(row.get("action", ""))
        risk_event = _clean_text(row.get("risk_event", ""))
        blocked_reason = _clean_text(row.get("blocked_reason", ""))
        order_text = orders.get(key, "")
        event_text = events.get(key, "")
        fill_text = fills.get(key, "")
        decision = _decision_label(
            action=action,
            order_text=order_text,
            risk_event=risk_event,
            blocked_reason=blocked_reason,
            executed_target_weight=executed_target_weight,
            current_weight=current_weight,
        )
        rows.append(
            {
                "bar": index + 1,
                "date": timestamp,
                "symbol": row.get("symbol", ""),
                "price": price,
                "executed_target_weight": executed_target_weight,
                "next_target_weight": next_target_weight,
                "current_weight": current_weight,
                "current_position_value": current_position_value,
                "action": action,
                "decision": decision,
                "risk_event": risk_event,
                "blocked_reason": blocked_reason,
                "order_status": event_text,
                "order": order_text,
                "fill": fill_text,
                "fill_price": row.get("fill_price"),
                "fill_quantity": row.get("fill_quantity"),
                "commission": row.get("commission"),
                "cash": cash,
                "position_quantity": position_quantity,
                "equity": equity,
                "drawdown": row.get("drawdown"),
                "timing_explanation": _timing_explanation(),
                "signal_explanation": _signal_explanation(
                    executed_target_weight,
                    next_target_weight,
                ),
                "risk_explanation": _risk_explanation(
                    risk_event=risk_event,
                    blocked_reason=blocked_reason,
                    order_text=order_text,
                    executed_target_weight=executed_target_weight,
                    current_weight=current_weight,
                ),
                "broker_explanation": _broker_explanation(
                    action=action,
                    order_text=order_text,
                    event_text=event_text,
                    fill_text=fill_text,
                ),
                "account_explanation": _account_explanation(
                    equity=equity,
                    cash=cash,
                    current_weight=current_weight,
                    position_quantity=position_quantity,
                    drawdown=_to_float(row.get("drawdown")),
                ),
                "step_summary": _step_summary(decision, action, risk_event, blocked_reason, fill_text),
            }
        )
    return pd.DataFrame(rows)


def replay_snapshot(replay: pd.DataFrame, position: int) -> dict[str, object]:
    if replay.empty:
        return {}
    position = max(0, min(int(position), len(replay) - 1))
    return replay.iloc[position].to_dict()


def replay_display_columns(replay: pd.DataFrame) -> list[str]:
    """Columnas mas utiles para leer el replay en UI sin perder auditabilidad."""
    preferred = [
        "bar",
        "date",
        "price",
        "decision",
        "executed_target_weight",
        "next_target_weight",
        "current_weight",
        "order",
        "fill",
        "risk_event",
        "blocked_reason",
        "cash",
        "position_quantity",
        "equity",
        "drawdown",
        "step_summary",
    ]
    return [column for column in preferred if column in replay.columns]


def _paper_strategy(request: PaperTradingRequest):
    if request.strategy_key == "buy_and_hold":
        return BuyAndHoldPaperStrategy()
    if request.strategy_key == "sma_cross":
        return MovingAverageCrossoverPaperStrategy(
            fast_window=int(request.strategy_parameters.get("fast_window", 20)),
            slow_window=int(request.strategy_parameters.get("slow_window", 200)),
            price_column=request.price_column,
        )
    if request.strategy_key == "rsi":
        return RSIPaperStrategy(
            window=int(request.strategy_parameters.get("window", 14)),
            oversold=float(request.strategy_parameters.get("oversold", 30.0)),
            overbought=float(request.strategy_parameters.get("overbought", 70.0)),
            price_column=request.price_column,
        )
    if request.strategy_key == "breakout":
        return BreakoutPaperStrategy(
            entry_window=int(request.strategy_parameters.get("entry_window", 55)),
            exit_window=int(request.strategy_parameters.get("exit_window", 20)),
            price_column=request.price_column,
        )
    if request.strategy_key == "trend_filter":
        return TrendFilterPaperStrategy(
            fast_window=int(request.strategy_parameters.get("fast_window", 20)),
            slow_window=int(request.strategy_parameters.get("slow_window", 100)),
            trend_window=int(request.strategy_parameters.get("trend_window", 200)),
            price_column=request.price_column,
        )
    raise ValueError("Estrategia no soportada por paper simulator.")


def _timestamp_key(value) -> str:
    timestamp = pd.Timestamp(value)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def _clean_text(value) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value)


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_pct(value: float) -> str:
    return f"{value:.1%}"


def _format_money(value: float) -> str:
    return f"{value:,.2f}"


def _decision_label(
    *,
    action: str,
    order_text: str,
    risk_event: str,
    blocked_reason: str,
    executed_target_weight: float,
    current_weight: float,
) -> str:
    if risk_event:
        return "Risk halt"
    if blocked_reason:
        return "Bloqueada por riesgo"
    if action == "buy":
        return "Compra ejecutada"
    if action == "sell":
        return "Venta ejecutada"
    if action == "dry_run":
        return "Orden dry-run"
    if action == "rejected":
        return "Orden rechazada"
    if order_text:
        return "Orden registrada"
    if abs(executed_target_weight - current_weight) <= 0.01:
        return "Mantener posicion"
    if executed_target_weight > current_weight:
        return "Sin compra material"
    if executed_target_weight < current_weight:
        return "Sin venta material"
    return "Esperar"


def _timing_explanation() -> str:
    return (
        "La orden de esta barra usa la senal pendiente calculada en la barra anterior. "
        "La senal calculada con el cierre actual queda para la proxima barra, evitando lookahead."
    )


def _signal_explanation(executed_target_weight: float, next_target_weight: float) -> str:
    return (
        f"Target aplicado ahora: {_format_pct(executed_target_weight)}. "
        f"Target que la estrategia deja para la proxima barra: {_format_pct(next_target_weight)}."
    )


def _risk_explanation(
    *,
    risk_event: str,
    blocked_reason: str,
    order_text: str,
    executed_target_weight: float,
    current_weight: float,
) -> str:
    if risk_event == "max_drawdown":
        return "El risk manager activo corte por max drawdown y fuerza salida o bloqueo de nuevas entradas."
    if risk_event:
        return f"El risk manager reporto evento de riesgo: {risk_event}."
    if blocked_reason == "trade_limit":
        return "El risk manager bloqueo la orden por limite de trades permitidos para el dia."
    if blocked_reason:
        return f"El risk manager bloqueo la orden: {blocked_reason}."
    if order_text:
        return "El risk manager permitio enviar una orden para acercar la posicion al target pendiente."
    if abs(executed_target_weight - current_weight) <= 0.01:
        return "No se envio orden porque la posicion ya estaba cerca del target pendiente."
    return (
        "No se envio orden. La diferencia contra el target probablemente fue menor al minimo operativo "
        "o no genero cantidad ejecutable."
    )


def _broker_explanation(*, action: str, order_text: str, event_text: str, fill_text: str) -> str:
    if fill_text:
        return f"FakeBroker lleno la orden simulada: {fill_text}."
    if action == "dry_run":
        return "FakeBroker recibio la orden, pero dry-run la cancelo intencionalmente sin fill."
    if action == "rejected":
        return f"FakeBroker rechazo la orden simulada. Evento: {event_text or 'sin detalle registrado'}."
    if order_text:
        return f"Hubo orden registrada sin fill final visible. Evento: {event_text or 'sin detalle registrado'}."
    return "FakeBroker no recibio orden en esta barra."


def _account_explanation(
    *,
    equity: float,
    cash: float,
    current_weight: float,
    position_quantity: float,
    drawdown: float,
) -> str:
    exposure = "con exposicion" if current_weight > 0.01 else "en cash o casi sin exposicion"
    return (
        f"Equity {_format_money(equity)}, cash {_format_money(cash)}, "
        f"posicion {position_quantity:.6g}, peso actual {_format_pct(current_weight)}; "
        f"la cuenta queda {exposure}. Drawdown actual {_format_pct(drawdown)}."
    )


def _step_summary(
    decision: str,
    action: str,
    risk_event: str,
    blocked_reason: str,
    fill_text: str,
) -> str:
    if risk_event or blocked_reason:
        reason = risk_event or blocked_reason
        return f"{decision}: la regla de riesgo domina la decision ({reason})."
    if fill_text:
        return f"{decision}: hubo fill simulado y la cuenta se actualizo."
    if action == "dry_run":
        return "Orden dry-run: se audito la orden, pero no impacto cash, posicion ni equity."
    if action == "rejected":
        return "Orden rechazada: no hubo cambio de posicion."
    return f"{decision}: no hubo ejecucion nueva en esta barra."


def _events_by_timestamp(events: pd.DataFrame) -> dict[str, str]:
    if events.empty or "timestamp" not in events:
        return {}
    frame = events.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    valid = frame.dropna(subset=["timestamp"])
    grouped = valid.groupby(valid["timestamp"].map(_timestamp_key))
    return {
        key: "; ".join(f"{row.status}: {row.message}" for row in group.itertuples())
        for key, group in grouped
    }


def _orders_by_timestamp(orders: pd.DataFrame) -> dict[str, str]:
    if orders.empty or "timestamp" not in orders:
        return {}
    frame = orders.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    valid = frame.dropna(subset=["timestamp"])
    grouped = valid.groupby(valid["timestamp"].map(_timestamp_key))
    return {
        key: "; ".join(
            f"#{row.order_id} {row.side} {float(row.quantity):.6g} ({row.status})"
            for row in group.itertuples()
        )
        for key, group in grouped
    }


def _fills_by_timestamp(fills: pd.DataFrame) -> dict[str, str]:
    if fills.empty or "timestamp" not in fills:
        return {}
    frame = fills.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    valid = frame.dropna(subset=["timestamp"])
    grouped = valid.groupby(valid["timestamp"].map(_timestamp_key))
    return {
        key: "; ".join(
            f"#{row.order_id} {row.side} {float(row.quantity):.6g} @ {float(row.price):.4g}"
            for row in group.itertuples()
        )
        for key, group in grouped
    }
