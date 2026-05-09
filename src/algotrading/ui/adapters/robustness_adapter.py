from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from algotrading.backtesting import BacktestConfig
from algotrading.backtesting import run_backtest
from algotrading.evaluation.diagnostics import (
    build_robustness_diagnostics,
    evaluate_multi_asset_train_test,
    evaluate_multi_asset_walk_forward,
)
from algotrading.experiments.runner import build_strategy_spec
from algotrading.strategies.buy_and_hold import generate_buy_and_hold_signals
from algotrading.strategies.registry import StrategySpec
from algotrading.ui.adapters.data_adapter import filter_by_dates, load_symbol_data


@dataclass(frozen=True)
class RobustnessRequest:
    symbols: tuple[str, ...]
    strategy_key: str
    strategy_parameters: dict[str, int | float]
    data_dir: Path | str = "data/raw"
    interval: str = "1d"
    start: str | None = None
    end: str | None = None
    price_column: str = "adj_close"
    initial_capital: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    train_ratio: float = 0.7
    run_walk_forward: bool = False
    run_regime_analysis: bool = False
    wf_train_rows: int = 756
    wf_test_rows: int = 252
    wf_step_rows: int = 252
    regime_min_rows: int = 60


@dataclass(frozen=True)
class RobustnessResult:
    train_test: pd.DataFrame
    walk_forward: pd.DataFrame
    diagnostics: pd.DataFrame
    regimes: pd.DataFrame


def run_robustness_request(request: RobustnessRequest) -> RobustnessResult:
    if not request.symbols:
        raise ValueError("Selecciona al menos un activo.")
    if not 0.1 <= request.train_ratio <= 0.9:
        raise ValueError("train_ratio debe estar entre 0.1 y 0.9.")

    frames = {}
    for symbol in request.symbols:
        frame, _ = load_symbol_data(request.data_dir, symbol, request.interval)
        frames[symbol] = filter_by_dates(frame, request.start, request.end)

    specs = _strategy_specs(request)
    config = BacktestConfig(
        initial_capital=request.initial_capital,
        commission_bps=request.commission_bps,
        slippage_bps=request.slippage_bps,
        price_column=request.price_column,
    )
    train_test = evaluate_multi_asset_train_test(
        frames=frames,
        strategy_specs=specs,
        config=config,
        train_ratio=request.train_ratio,
    )
    walk_forward = pd.DataFrame()
    if request.run_walk_forward:
        walk_forward = evaluate_multi_asset_walk_forward(
            frames=frames,
            strategy_specs=specs,
            config=config,
            train_rows=request.wf_train_rows,
            test_rows=request.wf_test_rows,
            step_rows=request.wf_step_rows,
        )
    diagnostics = build_robustness_diagnostics(
        train_test=train_test,
        walk_forward=walk_forward if not walk_forward.empty else None,
    )
    regimes = pd.DataFrame()
    if request.run_regime_analysis:
        regimes = evaluate_market_regimes(
            frames=frames,
            specs=specs,
            config=config,
            price_column=request.price_column,
            min_rows=request.regime_min_rows,
        )
    return RobustnessResult(
        train_test=train_test,
        walk_forward=walk_forward,
        diagnostics=diagnostics,
        regimes=regimes,
    )


def evaluate_market_regimes(
    frames: dict[str, pd.DataFrame],
    specs: list[StrategySpec],
    config: BacktestConfig,
    price_column: str = "adj_close",
    min_rows: int = 60,
) -> pd.DataFrame:
    """Evalua cada estrategia en anios/regimenes contiguos por activo."""
    if min_rows < 2:
        raise ValueError("regime_min_rows debe ser al menos 2.")
    rows = []
    for symbol, frame in frames.items():
        data = frame.copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data = data.sort_values("date").reset_index(drop=True)
        for year, period in data.groupby(data["date"].dt.year):
            period = period.reset_index(drop=True)
            if len(period) < min_rows:
                continue
            regime = _period_regime(period, price_column)
            for spec in specs:
                signal_frame = spec.function(period, signal_column=config.signal_column, **spec.parameters)
                result = run_backtest(signal_frame, config=config)
                metrics = result.metrics
                rows.append(
                    {
                        "symbol": symbol,
                        "year": int(year),
                        "regime": regime,
                        "strategy": spec.name,
                        "start_date": result.equity_curve["date"].iloc[0].strftime("%Y-%m-%d"),
                        "end_date": result.equity_curve["date"].iloc[-1].strftime("%Y-%m-%d"),
                        "rows": int(len(result.equity_curve)),
                        "total_return": metrics["total_return"],
                        "cagr": metrics["cagr"],
                        "sharpe_ratio": metrics["sharpe_ratio"],
                        "max_drawdown": metrics["max_drawdown"],
                        "number_of_trades": metrics["number_of_trades"],
                    }
                )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    benchmark = summary[summary["strategy"] == "buy_and_hold"][
        ["symbol", "year", "total_return", "max_drawdown"]
    ].rename(
        columns={
            "total_return": "buy_and_hold_return",
            "max_drawdown": "buy_and_hold_max_drawdown",
        }
    )
    merged = summary.merge(benchmark, on=["symbol", "year"], how="left")
    merged["vs_buy_and_hold_return"] = merged["total_return"] - merged["buy_and_hold_return"]
    merged["vs_buy_and_hold_drawdown"] = merged["max_drawdown"] - merged["buy_and_hold_max_drawdown"]
    return merged.sort_values(["symbol", "year", "strategy"]).reset_index(drop=True)


def regime_comment(regimes: pd.DataFrame) -> str:
    if regimes.empty:
        return "No hay suficientes periodos para analizar regimenes."
    subset = regimes[regimes["strategy"] != "buy_and_hold"]
    if subset.empty:
        return "Solo hay benchmark en regimenes."
    by_regime = subset.groupby("regime")["vs_buy_and_hold_return"].mean().sort_values()
    weakest = by_regime.index[0]
    strongest = by_regime.index[-1]
    if by_regime.min() < 0:
        return f"La estrategia se ve mas debil en regimen {weakest}; revisar si depende de un mercado especifico."
    return f"La estrategia no pierde contra benchmark en promedio por regimen; mejor regimen observado: {strongest}."


def robustness_comment(diagnostics: pd.DataFrame) -> str:
    if diagnostics.empty:
        return "No hay diagnostico suficiente."
    non_benchmark = diagnostics[diagnostics["strategy"] != "buy_and_hold"]
    if non_benchmark.empty:
        return "Solo se evaluo benchmark."
    best = non_benchmark.iloc[0]
    score = float(best.get("robustness_score", 0))
    flags = str(best.get("flags", ""))
    if score >= 75 and not flags:
        return "Resultado razonable para investigar mas, no para operar real."
    if "underperforms_benchmark" in flags:
        return "La estrategia pierde contra buy and hold en alguna prueba relevante."
    if "few_trades" in flags:
        return "Hay pocos trades; la robustez estadistica es debil."
    if "too_good_to_trust" in flags:
        return "Resultado llamativo: revisar datos, parametros y posible overfitting."
    return "Resultado mixto: conviene revisar ventanas, activos y benchmark."


def _strategy_specs(request: RobustnessRequest) -> list[StrategySpec]:
    return [
        StrategySpec("buy_and_hold", generate_buy_and_hold_signals, {}),
        build_strategy_spec(
            {
                "name": request.strategy_key,
                "parameters": request.strategy_parameters,
            },
            price_column=request.price_column,
        ),
    ]


def _period_regime(frame: pd.DataFrame, price_column: str) -> str:
    prices = pd.to_numeric(frame[price_column], errors="coerce")
    returns = prices.pct_change(fill_method=None).dropna()
    period_return = float(prices.iloc[-1] / prices.iloc[0] - 1)
    realized_volatility = float(returns.std() * (252**0.5)) if len(returns) else 0.0
    trend_label = "bull" if period_return >= 0 else "bear"
    volatility_label = "high_vol" if realized_volatility >= 0.25 else "low_vol"
    return f"{trend_label}_{volatility_label}"
