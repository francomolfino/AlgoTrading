from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import pandas as pd

from algotrading.backtesting import BacktestConfig, BacktestResult, run_backtest
from algotrading.metrics import calculate_cagr, calculate_drawdown, calculate_sharpe_ratio, calculate_total_return
from algotrading.ui.adapters.data_adapter import filter_by_dates, load_symbol_data
from algotrading.ui.adapters.strategy_adapter import generate_strategy_signals, validate_strategy_parameters


@dataclass(frozen=True)
class StressTestRequest:
    symbol: str
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
    remove_best_trades: int = 3


@dataclass(frozen=True)
class StressScenario:
    name: str
    method: str
    metrics: dict[str, float | int]
    equity_curve: pd.DataFrame
    note: str


@dataclass(frozen=True)
class StressTestResult:
    request: StressTestRequest
    scenarios: tuple[StressScenario, ...]
    comparison: pd.DataFrame
    conclusion: str
    flags: tuple[str, ...]


def run_stress_test_request(request: StressTestRequest) -> StressTestResult:
    _validate_request(request)
    frame, _ = load_symbol_data(request.data_dir, request.symbol, request.interval)
    frame = filter_by_dates(frame, request.start, request.end)
    if len(frame) < 4:
        raise ValueError("Se necesitan al menos cuatro filas para stress tests.")

    signal_frame = generate_strategy_signals(
        frame,
        strategy_key=request.strategy_key,
        parameters=request.strategy_parameters,
        price_column=request.price_column,
    )
    base_config = _config(request)
    base_result = run_backtest(signal_frame, config=base_config)

    scenarios = [
        _scenario_from_result(
            "Base",
            "backtest",
            base_result,
            "Backtest original con la configuracion elegida.",
        ),
        _scenario_from_result(
            "Comision x2",
            "backtest",
            run_backtest(signal_frame, config=_config(request, commission_bps=request.commission_bps * 2)),
            "Re-backtest con la comision duplicada.",
        ),
        _scenario_from_result(
            "Slippage x2",
            "backtest",
            run_backtest(signal_frame, config=_config(request, slippage_bps=request.slippage_bps * 2)),
            "Re-backtest con slippage duplicado.",
        ),
        _scenario_from_result(
            "Ejecucion +1 barra",
            "backtest",
            run_backtest(_delayed_signal_frame(signal_frame), config=base_config),
            "Re-backtest con una barra adicional de retraso antes de actuar.",
        ),
        _remove_best_trades_scenario(base_result, request.remove_best_trades),
        _remove_best_month_scenario(base_result),
    ]
    comparison = comparison_frame(scenarios)
    conclusion, flags = stress_conclusion(comparison)
    return StressTestResult(
        request=request,
        scenarios=tuple(scenarios),
        comparison=comparison,
        conclusion=conclusion,
        flags=tuple(flags),
    )


def comparison_frame(scenarios: list[StressScenario] | tuple[StressScenario, ...]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base_return = float(scenarios[0].metrics.get("total_return", math.nan)) if scenarios else math.nan
    base_drawdown = float(scenarios[0].metrics.get("max_drawdown", math.nan)) if scenarios else math.nan
    for scenario in scenarios:
        metrics = scenario.metrics
        total_return = _metric_float(metrics, "total_return")
        max_drawdown = _metric_float(metrics, "max_drawdown")
        rows.append(
            {
                "scenario": scenario.name,
                "method": scenario.method,
                "final_equity": _metric_float(metrics, "final_equity"),
                "total_return": total_return,
                "delta_return_vs_base": total_return - base_return,
                "cagr": _metric_float(metrics, "cagr"),
                "sharpe_ratio": _metric_float(metrics, "sharpe_ratio"),
                "max_drawdown": max_drawdown,
                "delta_drawdown_vs_base": max_drawdown - base_drawdown,
                "number_of_trades": int(metrics.get("number_of_trades", 0) or 0),
                "total_commissions": _metric_float(metrics, "total_commissions"),
                "note": scenario.note,
            }
        )
    return pd.DataFrame(rows)


def stress_conclusion(comparison: pd.DataFrame) -> tuple[str, list[str]]:
    if comparison.empty:
        return "No confiable", ["No hay escenarios para evaluar."]
    base = comparison.iloc[0]
    base_return = float(base["total_return"])
    base_trades = int(base["number_of_trades"])
    base_drawdown = float(base["max_drawdown"])
    stressed = comparison.iloc[1:]
    worst_return = float(stressed["total_return"].min()) if not stressed.empty else base_return
    worst_delta = float(stressed["delta_return_vs_base"].min()) if not stressed.empty else 0.0

    flags: list[str] = []
    if base_trades < 5:
        flags.append("Muy pocos trades: el stress test tiene poca muestra.")
    elif base_trades < 10:
        flags.append("Pocos trades: la evidencia sigue siendo fragil.")
    if base_drawdown <= -0.50:
        flags.append("Drawdown base mayor al 50%.")
    if base_return > 0 and worst_return < 0:
        flags.append("Al menos un stress vuelve negativo el retorno.")
    if abs(worst_delta) > max(0.20, abs(base_return) * 0.50):
        flags.append("El retorno cae demasiado frente al escenario base.")

    if base_trades < 5 or base_drawdown <= -0.50:
        return "No confiable", flags
    if flags:
        return "Fragil", flags
    return "Robusta", ["Sin quiebres obvios en estos stresses. No implica aptitud para operar real."]


def equity_curves_frame(scenarios: tuple[StressScenario, ...]) -> pd.DataFrame:
    frames = []
    for scenario in scenarios:
        equity = scenario.equity_curve[["date", "equity"]].copy()
        equity["date"] = pd.to_datetime(equity["date"])
        equity = equity.set_index("date").rename(columns={"equity": scenario.name})
        frames.append(equity)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index()


def _validate_request(request: StressTestRequest) -> None:
    if request.initial_capital <= 0:
        raise ValueError("Capital inicial debe ser mayor a cero.")
    if request.commission_bps < 0 or request.slippage_bps < 0:
        raise ValueError("Comision y slippage no pueden ser negativos.")
    if request.remove_best_trades < 0:
        raise ValueError("remove_best_trades no puede ser negativo.")
    validate_strategy_parameters(request.strategy_key, request.strategy_parameters)


def _config(
    request: StressTestRequest,
    *,
    commission_bps: float | None = None,
    slippage_bps: float | None = None,
) -> BacktestConfig:
    return BacktestConfig(
        initial_capital=float(request.initial_capital),
        commission_bps=float(request.commission_bps if commission_bps is None else commission_bps),
        slippage_bps=float(request.slippage_bps if slippage_bps is None else slippage_bps),
        price_column=request.price_column,
    )


def _delayed_signal_frame(signal_frame: pd.DataFrame) -> pd.DataFrame:
    delayed = signal_frame.copy()
    delayed["signal"] = pd.to_numeric(delayed["signal"], errors="coerce").shift(1).fillna(0).astype(int)
    return delayed


def _scenario_from_result(name: str, method: str, result: BacktestResult, note: str) -> StressScenario:
    return StressScenario(
        name=name,
        method=method,
        metrics=dict(result.metrics),
        equity_curve=result.equity_curve.copy(),
        note=note,
    )


def _remove_best_trades_scenario(base_result: BacktestResult, trade_count: int) -> StressScenario:
    if trade_count <= 0 or base_result.trades.empty or "pnl" not in base_result.trades:
        return _post_hoc_scenario(
            "Sin mejores trades",
            base_result,
            base_result.equity_curve.copy(),
            "No se quitaron trades positivos.",
        )

    best_trades = base_result.trades[base_result.trades["pnl"] > 0].nlargest(trade_count, "pnl")
    adjusted = base_result.equity_curve.copy()
    adjusted["date"] = pd.to_datetime(adjusted["date"])
    for _, trade in best_trades.iterrows():
        exit_date = pd.Timestamp(trade["exit_date"])
        pnl = float(trade["pnl"])
        adjusted.loc[adjusted["date"] >= exit_date, "equity"] -= pnl
    adjusted["equity"] = adjusted["equity"].clip(lower=0.01)
    note = f"Shock post-hoc: se restaron los {len(best_trades)} mejores PnL desde su fecha de salida."
    return _post_hoc_scenario(f"Sin mejores {len(best_trades)} trades", base_result, adjusted, note)


def _remove_best_month_scenario(base_result: BacktestResult) -> StressScenario:
    equity = base_result.equity_curve.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    daily_returns = pd.to_numeric(equity["daily_return"], errors="coerce").fillna(0.0)
    monthly_returns = (1 + daily_returns).groupby(equity["date"].dt.to_period("M")).prod() - 1
    positive_months = monthly_returns[monthly_returns > 0]
    if positive_months.empty:
        return _post_hoc_scenario(
            "Sin mejor mes",
            base_result,
            equity,
            "No habia meses positivos para remover.",
        )
    best_month = positive_months.idxmax()
    stressed_returns = daily_returns.copy()
    stressed_returns.loc[equity["date"].dt.to_period("M") == best_month] = 0.0
    adjusted = equity.copy()
    adjusted["equity"] = base_result.config.initial_capital * (1 + stressed_returns).cumprod()
    note = f"Shock post-hoc: retornos diarios del mejor mes ({best_month}) reemplazados por 0%."
    return _post_hoc_scenario("Sin mejor mes", base_result, adjusted, note)


def _post_hoc_scenario(
    name: str,
    base_result: BacktestResult,
    adjusted_equity: pd.DataFrame,
    note: str,
) -> StressScenario:
    equity = adjusted_equity.copy()
    equity["date"] = pd.to_datetime(equity["date"])
    equity["equity"] = pd.to_numeric(equity["equity"], errors="coerce").clip(lower=0.01)
    equity["daily_return"] = equity["equity"].pct_change(fill_method=None).fillna(0.0)
    equity["drawdown"] = calculate_drawdown(equity["equity"])
    metrics = dict(base_result.metrics)
    metrics["final_equity"] = float(equity["equity"].iloc[-1])
    metrics["total_return"] = calculate_total_return(
        float(base_result.config.initial_capital),
        float(metrics["final_equity"]),
    )
    metrics["cagr"] = calculate_cagr(
        initial_value=float(base_result.config.initial_capital),
        final_value=float(metrics["final_equity"]),
        start_date=equity["date"].iloc[0],
        end_date=equity["date"].iloc[-1],
    )
    metrics["sharpe_ratio"] = calculate_sharpe_ratio(
        equity["daily_return"],
        periods_per_year=base_result.config.periods_per_year,
    )
    metrics["max_drawdown"] = float(equity["drawdown"].min())
    metrics["excess_return_vs_benchmark"] = float(
        metrics["total_return"] - metrics.get("benchmark_total_return", 0.0)
    )
    return StressScenario(name=name, method="post-hoc", metrics=metrics, equity_curve=equity, note=note)


def _metric_float(metrics: dict[str, float | int], key: str) -> float:
    try:
        return float(metrics.get(key, math.nan))
    except (TypeError, ValueError):
        return math.nan
