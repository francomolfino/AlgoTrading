from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import pandas as pd

from algotrading.backtesting import BacktestResult
from algotrading.ui.adapters.experiment_adapter import ExperimentDetails


@dataclass(frozen=True)
class ResearchVerdict:
    reliability: str
    benchmark_status: str
    summary: str
    flags: tuple[str, ...]
    next_action: str
    diagnostics: tuple[tuple[str, str], ...]


def build_research_verdict_from_result(
    result: BacktestResult,
    *,
    parameter_count: int,
    symbol_count: int,
) -> ResearchVerdict:
    return _build_research_verdict(
        metrics=result.metrics,
        equity=result.equity_curve,
        parameter_count=parameter_count,
        symbol_count=symbol_count,
    )


def build_research_verdict_from_details(details: ExperimentDetails) -> ResearchVerdict:
    parameters = details.config.get("strategy", {}).get("parameters", {})
    parameter_count = len(parameters) if isinstance(parameters, Mapping) else 0
    symbols = details.config.get("symbols", [])
    symbol_count = len(symbols) if isinstance(symbols, (list, tuple)) else 1
    return _build_research_verdict(
        metrics=details.metrics,
        equity=details.equity,
        parameter_count=parameter_count,
        symbol_count=symbol_count,
    )


def _build_research_verdict(
    *,
    metrics: Mapping[str, Any],
    equity: pd.DataFrame,
    parameter_count: int,
    symbol_count: int,
) -> ResearchVerdict:
    trades = _metric_int(metrics, "number_of_trades")
    max_drawdown = _metric_float(metrics, "max_drawdown")
    sharpe = _metric_float(metrics, "sharpe_ratio")
    excess_return = _metric_float(metrics, "excess_return_vs_benchmark")
    years = _years_from_equity(equity)

    flags: list[str] = []
    if trades < 10:
        flags.append("Pocos trades: la muestra es chica para confiar en las metricas.")
    if years < 1:
        flags.append("Periodo corto: menos de un ano de datos no alcanza para validar una idea.")
    if max_drawdown <= -0.25:
        flags.append("Drawdown peligroso: la caida maxima supera el 25%.")
    if excess_return < 0:
        flags.append("No supera benchmark/buy and hold en este periodo.")
    if sharpe > 3:
        flags.append("Sharpe sospechosamente alto: revisar overfitting, datos y costos.")
    if parameter_count > 4:
        flags.append("Muchos parametros: mayor riesgo de sobreoptimizacion.")
    if symbol_count <= 1:
        flags.append("Probado en un solo activo: falta validacion multi-activo.")

    reliability = _reliability_label(
        trades=trades,
        years=years,
        max_drawdown=max_drawdown,
        excess_return=excess_return,
        parameter_count=parameter_count,
        symbol_count=symbol_count,
    )
    benchmark_status = _benchmark_status(excess_return)
    summary = _summary(reliability, flags)
    next_action = _next_action(
        trades=trades,
        years=years,
        max_drawdown=max_drawdown,
        excess_return=excess_return,
        parameter_count=parameter_count,
        symbol_count=symbol_count,
    )

    diagnostics = (
        ("Trades cerrados", str(trades)),
        ("Anios aprox.", f"{years:.1f}"),
        ("Exceso vs benchmark", _format_percent(excess_return)),
        ("Max drawdown", _format_percent(max_drawdown)),
        ("Parametros", str(parameter_count)),
        ("Activos", str(symbol_count)),
    )
    return ResearchVerdict(
        reliability=reliability,
        benchmark_status=benchmark_status,
        summary=summary,
        flags=tuple(flags),
        next_action=next_action,
        diagnostics=diagnostics,
    )


def _reliability_label(
    *,
    trades: int,
    years: float,
    max_drawdown: float,
    excess_return: float,
    parameter_count: int,
    symbol_count: int,
) -> str:
    penalties = 0
    penalties += 2 if trades < 10 else 0
    penalties += 2 if years < 1 else 0
    penalties += 1 if max_drawdown <= -0.25 else 0
    penalties += 1 if excess_return < 0 else 0
    penalties += 1 if parameter_count > 4 else 0
    penalties += 1 if symbol_count <= 1 else 0
    if penalties >= 4:
        return "Baja"
    if penalties >= 2:
        return "Media"
    return "Preliminar alta"


def _benchmark_status(excess_return: float) -> str:
    if math.isnan(excess_return):
        return "Sin benchmark"
    if excess_return > 0.01:
        return "Supera benchmark"
    if excess_return < -0.01:
        return "Pierde contra benchmark"
    return "Similar al benchmark"


def _summary(reliability: str, flags: list[str]) -> str:
    if reliability == "Baja":
        return "Resultado util para aprender, pero todavia debil como evidencia de investigacion."
    if flags:
        return "Resultado investigable, con puntos concretos que revisar antes de confiar."
    return "No aparecen alertas obvias, pero falta robustez antes de pensar en paper trading serio."


def _next_action(
    *,
    trades: int,
    years: float,
    max_drawdown: float,
    excess_return: float,
    parameter_count: int,
    symbol_count: int,
) -> str:
    if years < 1:
        return "Ampliar el periodo de datos y repetir el backtest."
    if trades < 10:
        return "Buscar mas muestras: mas anos, mas activos o parametros menos restrictivos."
    if parameter_count > 4:
        return "Reducir parametros y correr sensibilidad/robustez."
    if symbol_count <= 1:
        return "Probar multi-activo y separar in-sample/out-of-sample."
    if max_drawdown <= -0.25:
        return "Revisar risk management y comparar retorno ajustado por riesgo."
    if excess_return < 0:
        return "Explicar por que la estrategia pierde contra buy and hold antes de seguir optimizando."
    return "Correr train/test, walk-forward y stress tests."


def _years_from_equity(equity: pd.DataFrame) -> float:
    if equity.empty:
        return 0.0
    if "date" in equity.columns:
        dates = pd.to_datetime(equity["date"], errors="coerce").dropna()
        if len(dates) >= 2:
            days = max((dates.max() - dates.min()).days, 0)
            if days > 0:
                return days / 365.25
    return len(equity) / 252


def _metric_float(metrics: Mapping[str, Any], key: str) -> float:
    try:
        value = float(metrics.get(key, math.nan))
    except (TypeError, ValueError):
        return math.nan
    return value


def _metric_int(metrics: Mapping[str, Any], key: str) -> int:
    try:
        return int(metrics.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _format_percent(value: float) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value:.2%}"
