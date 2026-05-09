from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
