from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import pandas as pd

from algotrading.backtesting import BacktestResult
from algotrading.ui.adapters.experiment_adapter import ExperimentDetails


@dataclass(frozen=True)
class EvidenceComponent:
    name: str
    score: float
    weight: float
    status: str
    explanation: str


@dataclass(frozen=True)
class EvidenceScore:
    score: float
    label: str
    explanation: str
    components: tuple[EvidenceComponent, ...]


def build_evidence_score_from_result(
    result: BacktestResult,
    *,
    parameter_count: int,
    symbol_count: int,
    strategy_key: str | None = None,
    symbol: str | None = None,
    robustness_result: Any | None = None,
    stress_result: Any | None = None,
) -> EvidenceScore:
    robustness_row = _matching_robustness_row(robustness_result, strategy_key=strategy_key, symbol=symbol)
    return _build_evidence_score(
        metrics=result.metrics,
        equity=result.equity_curve,
        parameter_count=parameter_count,
        symbol_count=max(symbol_count, _robustness_symbol_count(robustness_result, strategy_key)),
        commission_bps=float(result.config.commission_bps),
        slippage_bps=float(result.config.slippage_bps),
        robustness_row=robustness_row,
        stress_result=stress_result,
    )


def build_evidence_score_from_details(
    details: ExperimentDetails,
    *,
    robustness_result: Any | None = None,
    stress_result: Any | None = None,
) -> EvidenceScore:
    strategy_config = details.config.get("strategy", {})
    parameters = strategy_config.get("parameters", {})
    parameter_count = len(parameters) if isinstance(parameters, Mapping) else 0
    symbols = details.config.get("symbols", [])
    symbol_count = len(symbols) if isinstance(symbols, (list, tuple)) else 1
    backtest_config = details.config.get("backtest", {})
    strategy_key = str(strategy_config.get("name", "")) or None
    robustness_row = _matching_robustness_row(robustness_result, strategy_key=strategy_key, symbol=details.symbol)

    return _build_evidence_score(
        metrics=details.metrics,
        equity=details.equity,
        parameter_count=parameter_count,
        symbol_count=max(symbol_count, _robustness_symbol_count(robustness_result, strategy_key)),
        commission_bps=_safe_float(backtest_config.get("commission_bps"), 0.0),
        slippage_bps=_safe_float(backtest_config.get("slippage_bps"), 0.0),
        robustness_row=robustness_row,
        stress_result=stress_result,
    )


def components_frame(score: EvidenceScore) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "componente": component.name,
                "score": round(component.score, 1),
                "peso": f"{component.weight:.0f}%",
                "estado": component.status,
                "lectura": component.explanation,
            }
            for component in score.components
        ]
    )


def _build_evidence_score(
    *,
    metrics: Mapping[str, Any],
    equity: pd.DataFrame,
    parameter_count: int,
    symbol_count: int,
    commission_bps: float,
    slippage_bps: float,
    robustness_row: pd.Series | None,
    stress_result: Any | None,
) -> EvidenceScore:
    components = (
        _trades_component(_metric_int(metrics, "number_of_trades")),
        _years_component(_years_from_equity(equity)),
        _out_of_sample_component(robustness_row),
        _walk_forward_component(robustness_row),
        _multi_asset_component(symbol_count),
        _benchmark_component(_metric_float(metrics, "excess_return_vs_benchmark")),
        _drawdown_component(_metric_float(metrics, "max_drawdown")),
        _costs_component(commission_bps, slippage_bps),
        _parameters_component(parameter_count),
        _stress_component(stress_result),
    )
    weighted = sum(component.score * component.weight for component in components) / 100
    final_score = round(max(0.0, min(100.0, weighted)), 1)
    return EvidenceScore(
        score=final_score,
        label=_score_label(final_score),
        explanation=_score_explanation(final_score),
        components=components,
    )


def _trades_component(trades: int) -> EvidenceComponent:
    if trades >= 30:
        score, status = 100.0, "bien"
    elif trades >= 10:
        score, status = 70.0, "aceptable"
    elif trades > 0:
        score, status = 35.0, "debil"
    else:
        score, status = 0.0, "sin evidencia"
    return EvidenceComponent(
        "Cantidad de trades",
        score,
        12,
        status,
        f"{trades} trades cerrados; pocas operaciones vuelven inestables las metricas.",
    )


def _years_component(years: float) -> EvidenceComponent:
    if years >= 5:
        score, status = 100.0, "bien"
    elif years >= 3:
        score, status = 80.0, "aceptable"
    elif years >= 1:
        score, status = 55.0, "limitado"
    elif years > 0:
        score, status = 25.0, "debil"
    else:
        score, status = 0.0, "sin datos"
    return EvidenceComponent(
        "Anios de datos",
        score,
        12,
        status,
        f"{years:.1f} anios aproximados; mas ciclos ayudan a detectar fragilidad.",
    )


def _out_of_sample_component(row: pd.Series | None) -> EvidenceComponent:
    if row is None:
        return EvidenceComponent(
            "Out-of-sample",
            0.0,
            14,
            "no corrido",
            "No hay train/test asociado a este resultado.",
        )

    vs_benchmark = _safe_float(row.get("test_vs_buy_and_hold_return"), math.nan)
    gap = abs(_safe_float(row.get("abs_train_test_return_gap"), math.nan))
    test_trades = _safe_float(row.get("test_number_of_trades"), 0.0)
    score = 60.0
    if not math.isnan(vs_benchmark):
        score += 25 if vs_benchmark >= 0 else -25
    if not math.isnan(gap):
        score -= min(gap * 100, 30)
    if test_trades < 5:
        score -= 15
    score = _clamp(score)
    status = "bien" if score >= 75 else "mixto" if score >= 45 else "debil"
    return EvidenceComponent(
        "Out-of-sample",
        score,
        14,
        status,
        "Usa el resultado de test contra buy and hold y la brecha train/test.",
    )


def _walk_forward_component(row: pd.Series | None) -> EvidenceComponent:
    if row is None:
        return EvidenceComponent(
            "Walk-forward",
            0.0,
            10,
            "no corrido",
            "No hay ventanas walk-forward asociadas.",
        )

    windows = int(_safe_float(row.get("walk_forward_windows"), 0.0))
    positive_rate = _safe_float(row.get("walk_forward_positive_rate"), math.nan)
    avg_vs_benchmark = _safe_float(row.get("walk_forward_avg_vs_buy_and_hold"), math.nan)
    if windows <= 0 or math.isnan(positive_rate):
        score, status = 0.0, "no corrido"
    else:
        score = min(100.0, windows / 3 * 40) + max(0.0, positive_rate) * 45
        if not math.isnan(avg_vs_benchmark):
            score += 15 if avg_vs_benchmark >= 0 else -15
        score = _clamp(score)
        status = "bien" if score >= 75 else "mixto" if score >= 45 else "debil"
    return EvidenceComponent(
        "Walk-forward",
        score,
        10,
        status,
        f"{windows} ventanas; mira estabilidad temporal, no solo un split.",
    )


def _multi_asset_component(symbol_count: int) -> EvidenceComponent:
    if symbol_count >= 4:
        score, status = 100.0, "bien"
    elif symbol_count >= 2:
        score, status = 70.0, "aceptable"
    elif symbol_count == 1:
        score, status = 0.0, "un solo activo"
    else:
        score, status = 0.0, "sin activos"
    return EvidenceComponent(
        "Validacion multi-activo",
        score,
        10,
        status,
        f"{symbol_count} activo(s) considerados; un solo ticker puede enganar.",
    )


def _benchmark_component(excess_return: float) -> EvidenceComponent:
    if math.isnan(excess_return):
        return EvidenceComponent("Benchmark", 0.0, 13, "sin benchmark", "No hay comparacion disponible.")
    if excess_return > 0.02:
        score, status = 100.0, "supera"
    elif excess_return >= -0.02:
        score, status = 60.0, "similar"
    else:
        score, status = 25.0, "pierde"
    return EvidenceComponent(
        "Comparacion con benchmark",
        score,
        13,
        status,
        f"Exceso vs benchmark: {excess_return:.2%}.",
    )


def _drawdown_component(max_drawdown: float) -> EvidenceComponent:
    if math.isnan(max_drawdown):
        return EvidenceComponent("Drawdown", 0.0, 10, "sin dato", "No hay max drawdown calculado.")
    drawdown = abs(max_drawdown)
    if drawdown <= 0.10:
        score, status = 100.0, "controlado"
    elif drawdown <= 0.25:
        score, status = 70.0, "moderado"
    elif drawdown <= 0.50:
        score, status = 35.0, "alto"
    else:
        score, status = 10.0, "muy alto"
    return EvidenceComponent("Drawdown", score, 10, status, f"Max drawdown observado: {-drawdown:.2%}.")


def _costs_component(commission_bps: float, slippage_bps: float) -> EvidenceComponent:
    if commission_bps > 0 and slippage_bps > 0:
        score, status = 100.0, "incluidos"
    elif commission_bps > 0 or slippage_bps > 0:
        score, status = 60.0, "parcial"
    else:
        score, status = 0.0, "sin costos"
    return EvidenceComponent(
        "Costos incluidos",
        score,
        4,
        status,
        f"Comision {commission_bps:.2f} bps, slippage {slippage_bps:.2f} bps.",
    )


def _parameters_component(parameter_count: int) -> EvidenceComponent:
    if parameter_count <= 2:
        score, status = 100.0, "simple"
    elif parameter_count <= 4:
        score, status = 75.0, "razonable"
    elif parameter_count <= 6:
        score, status = 40.0, "complejo"
    else:
        score, status = 10.0, "sobreajuste probable"
    return EvidenceComponent(
        "Cantidad de parametros",
        score,
        5,
        status,
        f"{parameter_count} parametro(s); mas knobs aumentan el riesgo de overfitting.",
    )


def _stress_component(stress_result: Any | None) -> EvidenceComponent:
    if stress_result is None:
        return EvidenceComponent(
            "Stress tests",
            50.0,
            10,
            "no corrido",
            "Sin stress test compatible. Este componente queda neutral hasta correrlo.",
        )

    conclusion = str(getattr(stress_result, "conclusion", ""))
    comparison = getattr(stress_result, "comparison", pd.DataFrame())
    worst_delta = _worst_stress_delta(comparison)
    if conclusion == "Robusta":
        score, status = 90.0, "robusta"
    elif conclusion == "Fragil":
        score, status = 25.0, "fragil"
    elif conclusion == "No confiable":
        score, status = 5.0, "no confiable"
    else:
        score, status = 35.0, "indeterminado"

    explanation = f"Conclusion stress: {conclusion or 'n/a'}."
    if not math.isnan(worst_delta):
        explanation += f" Peor delta vs base: {worst_delta:.2%}."
    return EvidenceComponent("Stress tests", score, 10, status, explanation)


def _matching_robustness_row(
    robustness_result: Any | None,
    *,
    strategy_key: str | None,
    symbol: str | None,
) -> pd.Series | None:
    diagnostics = getattr(robustness_result, "diagnostics", None)
    if diagnostics is None or diagnostics.empty:
        return None
    subset = diagnostics
    if strategy_key and "strategy" in subset.columns:
        subset = subset[_strategy_matches(subset["strategy"], strategy_key)]
    elif "strategy" in subset.columns:
        subset = subset[subset["strategy"].astype(str) != "buy_and_hold"]
    if symbol and "symbol" in subset.columns:
        symbol_subset = subset[subset["symbol"].astype(str) == symbol]
        if not symbol_subset.empty:
            subset = symbol_subset
    if subset.empty:
        return None
    return subset.iloc[0]


def _worst_stress_delta(comparison: pd.DataFrame) -> float:
    if comparison is None or comparison.empty or "delta_return_vs_base" not in comparison.columns:
        return math.nan
    deltas = pd.to_numeric(comparison["delta_return_vs_base"], errors="coerce").dropna()
    if deltas.empty:
        return math.nan
    return float(deltas.min())


def _robustness_symbol_count(robustness_result: Any | None, strategy_key: str | None) -> int:
    diagnostics = getattr(robustness_result, "diagnostics", None)
    if diagnostics is None or diagnostics.empty or "symbol" not in diagnostics.columns:
        return 0
    subset = diagnostics
    if strategy_key and "strategy" in subset.columns:
        subset = subset[_strategy_matches(subset["strategy"], strategy_key)]
    return int(subset["symbol"].nunique()) if not subset.empty else 0


def _strategy_matches(values: pd.Series, strategy_key: str) -> pd.Series:
    strategies = values.astype(str)
    if strategy_key == "buy_and_hold":
        return strategies == "buy_and_hold"
    return (strategies == strategy_key) | strategies.str.startswith(f"{strategy_key}_")


def _score_label(score: float) -> str:
    if score >= 75:
        return "Evidencia fuerte para seguir investigando"
    if score >= 50:
        return "Evidencia mixta"
    if score >= 25:
        return "Evidencia debil"
    return "Evidencia insuficiente"


def _score_explanation(score: float) -> str:
    if score >= 75:
        return "La evidencia luce razonable, pero igual falta paper trading simulado antes de cualquier paso real."
    if score >= 50:
        return "Hay senales utiles, aunque todavia faltan pruebas de robustez o muestra mas amplia."
    if score >= 25:
        return "Sirve como aprendizaje o hipotesis inicial; no alcanza para confiar en la estrategia."
    return "Todavia no hay evidencia suficiente. Prioriza datos, benchmark y validaciones fuera de muestra."


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
    return _safe_float(metrics.get(key), math.nan)


def _metric_int(metrics: Mapping[str, Any], key: str) -> int:
    try:
        return int(metrics.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if not math.isinf(result) else default


def _clamp(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return max(0.0, min(100.0, round(value, 1)))
