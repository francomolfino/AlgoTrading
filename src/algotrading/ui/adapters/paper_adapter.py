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
        rows.append(
            {
                "bar": index + 1,
                "date": timestamp,
                "symbol": row.get("symbol", ""),
                "price": row.get("price"),
                "executed_target_weight": row.get("executed_target_weight"),
                "next_target_weight": row.get("next_target_weight"),
                "action": row.get("action", ""),
                "risk_event": row.get("risk_event", ""),
                "blocked_reason": row.get("blocked_reason", ""),
                "order_status": events.get(key, ""),
                "order": orders.get(key, ""),
                "fill": fills.get(key, ""),
                "fill_price": row.get("fill_price"),
                "fill_quantity": row.get("fill_quantity"),
                "commission": row.get("commission"),
                "cash": row.get("cash"),
                "position_quantity": row.get("position_quantity"),
                "equity": row.get("equity"),
                "drawdown": row.get("drawdown"),
            }
        )
    return pd.DataFrame(rows)


def replay_snapshot(replay: pd.DataFrame, position: int) -> dict[str, object]:
    if replay.empty:
        return {}
    position = max(0, min(int(position), len(replay) - 1))
    return replay.iloc[position].to_dict()


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
