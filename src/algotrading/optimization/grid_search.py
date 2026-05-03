from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import product
import json

import pandas as pd

from algotrading.backtesting import BacktestConfig
from algotrading.evaluation import evaluate_train_test
from algotrading.strategies import (
    generate_buy_and_hold_signals,
    generate_rsi_signals,
    generate_sma_crossover_signals,
)
from algotrading.strategies.registry import StrategySpec


@dataclass(frozen=True)
class OptimizationCandidate:
    family: str
    spec: StrategySpec


@dataclass(frozen=True)
class OptimizationSearchResult:
    ranking: pd.DataFrame
    period_results: pd.DataFrame


def build_sma_candidates(
    fast_windows: Iterable[int],
    slow_windows: Iterable[int],
    price_column: str = "adj_close",
) -> list[OptimizationCandidate]:
    candidates: list[OptimizationCandidate] = []
    for fast_window, slow_window in product(fast_windows, slow_windows):
        if fast_window <= 0 or slow_window <= 0:
            raise ValueError("Las ventanas SMA deben ser positivas.")
        if fast_window >= slow_window:
            continue
        spec = StrategySpec(
            name=f"sma_cross_{fast_window}_{slow_window}",
            function=generate_sma_crossover_signals,
            parameters={
                "fast_window": fast_window,
                "slow_window": slow_window,
                "price_column": price_column,
            },
        )
        candidates.append(OptimizationCandidate(family="sma_cross", spec=spec))

    if not candidates:
        raise ValueError("No quedaron combinaciones SMA validas. Revisa fast < slow.")
    return candidates


def build_rsi_candidates(
    windows: Iterable[int],
    threshold_pairs: Iterable[tuple[float, float]],
    price_column: str = "adj_close",
) -> list[OptimizationCandidate]:
    candidates: list[OptimizationCandidate] = []
    for window, (oversold, overbought) in product(windows, threshold_pairs):
        if window <= 0:
            raise ValueError("Las ventanas RSI deben ser positivas.")
        if not 0 <= oversold < overbought <= 100:
            raise ValueError("Los umbrales RSI requieren 0 <= oversold < overbought <= 100.")
        spec = StrategySpec(
            name=f"rsi_{window}_{_number_label(oversold)}_{_number_label(overbought)}",
            function=generate_rsi_signals,
            parameters={
                "window": window,
                "oversold": oversold,
                "overbought": overbought,
                "price_column": price_column,
            },
        )
        candidates.append(OptimizationCandidate(family="rsi", spec=spec))

    if not candidates:
        raise ValueError("No quedaron combinaciones RSI validas.")
    return candidates


def validate_candidate_count(
    candidates: Sequence[OptimizationCandidate],
    max_combinations: int = 30,
) -> int:
    if max_combinations <= 0:
        raise ValueError("max_combinations debe ser mayor a cero.")
    total = len(candidates)
    if total == 0:
        raise ValueError("No hay candidatos para evaluar.")
    if total > max_combinations:
        raise ValueError(
            f"Demasiadas combinaciones: {total}. Limite educativo: {max_combinations}."
        )
    return total


def run_controlled_search(
    frame: pd.DataFrame,
    candidates: Sequence[OptimizationCandidate],
    config: BacktestConfig,
    train_ratio: float = 0.7,
    warmup_bars: int = 260,
    max_combinations: int = 30,
) -> OptimizationSearchResult:
    validate_candidate_count(candidates, max_combinations=max_combinations)
    benchmark = StrategySpec(
        name="buy_and_hold",
        function=generate_buy_and_hold_signals,
        parameters={},
    )
    specs = [benchmark, *[candidate.spec for candidate in candidates]]
    period_results = evaluate_train_test(
        frame=frame,
        strategy_specs=specs,
        config=config,
        train_ratio=train_ratio,
        warmup_bars=warmup_bars,
    )
    ranking = _rank_candidates(period_results, candidates)
    return OptimizationSearchResult(ranking=ranking, period_results=period_results)


def _rank_candidates(
    period_results: pd.DataFrame,
    candidates: Sequence[OptimizationCandidate],
) -> pd.DataFrame:
    rows = []
    for candidate in candidates:
        train = _single_period_row(period_results, candidate.spec.name, "train")
        test = _single_period_row(period_results, candidate.spec.name, "test")
        test_gap = float(train["total_return"] - test["total_return"])
        abs_gap = abs(test_gap)
        row = {
            "strategy": candidate.spec.name,
            "family": candidate.family,
            "parameters": json.dumps(candidate.spec.parameters, sort_keys=True),
            "train_total_return": train["total_return"],
            "test_total_return": test["total_return"],
            "train_cagr": train["cagr"],
            "test_cagr": test["cagr"],
            "test_sharpe_ratio": test["sharpe_ratio"],
            "train_max_drawdown": train["max_drawdown"],
            "test_max_drawdown": test["max_drawdown"],
            "test_number_of_trades": test["number_of_trades"],
            "test_win_rate": test["win_rate"],
            "test_vs_buy_and_hold_return": test["vs_buy_and_hold_return"],
            "test_vs_buy_and_hold_drawdown": test["vs_buy_and_hold_drawdown"],
            "train_test_return_gap": test_gap,
            "abs_train_test_return_gap": abs_gap,
        }
        row["comment"] = _candidate_comment(row)
        rows.append(row)

    ranking = pd.DataFrame(rows)
    ranking = ranking.sort_values(
        by=[
            "test_vs_buy_and_hold_return",
            "abs_train_test_return_gap",
            "test_max_drawdown",
            "test_sharpe_ratio",
        ],
        ascending=[False, True, False, False],
        na_position="last",
    ).reset_index(drop=True)
    ranking.insert(0, "rank", range(1, len(ranking) + 1))
    return ranking


def _single_period_row(period_results: pd.DataFrame, strategy: str, period: str) -> pd.Series:
    rows = period_results[
        (period_results["strategy"] == strategy) & (period_results["period"] == period)
    ]
    if len(rows) != 1:
        raise ValueError(f"Esperaba una fila para {strategy}/{period}, encontre {len(rows)}.")
    return rows.iloc[0]


def _candidate_comment(row: dict[str, float | int | str]) -> str:
    test_return = float(row["test_total_return"])
    test_vs_benchmark = float(row["test_vs_buy_and_hold_return"])
    abs_gap = float(row["abs_train_test_return_gap"])
    drawdown_delta = float(row["test_vs_buy_and_hold_drawdown"])

    if test_return < 0:
        return "Descartar: pierde dinero en test."
    if test_vs_benchmark >= 0 and abs_gap <= 0.25:
        return "Interesante: compite con benchmark en test y gap train/test moderado."
    if test_vs_benchmark >= 0:
        return "Supera benchmark en test, pero revisar posible inestabilidad train/test."
    if drawdown_delta > 0:
        return "No supera retorno de benchmark, pero reduce drawdown en test."
    return "No supera benchmark en test."


def _number_label(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value).replace(".", "p")
