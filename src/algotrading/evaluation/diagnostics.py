from __future__ import annotations

from collections.abc import Mapping
import json
import math

import pandas as pd

from algotrading.backtesting import BacktestConfig
from algotrading.evaluation.robustness import evaluate_train_test, evaluate_walk_forward
from algotrading.strategies.registry import StrategySpec


def evaluate_multi_asset_train_test(
    frames: Mapping[str, pd.DataFrame],
    strategy_specs: list[StrategySpec],
    config: BacktestConfig,
    train_ratio: float = 0.7,
    warmup_bars: int = 260,
) -> pd.DataFrame:
    """Ejecuta train/test por activo y agrega columna symbol."""
    rows = []
    for symbol, frame in frames.items():
        summary = evaluate_train_test(
            frame=frame,
            strategy_specs=strategy_specs,
            config=config,
            train_ratio=train_ratio,
            warmup_bars=warmup_bars,
        )
        summary.insert(0, "symbol", symbol)
        rows.append(summary)
    if not rows:
        raise ValueError("Se requiere al menos un activo.")
    return pd.concat(rows, ignore_index=True)


def evaluate_multi_asset_walk_forward(
    frames: Mapping[str, pd.DataFrame],
    strategy_specs: list[StrategySpec],
    config: BacktestConfig,
    train_rows: int = 756,
    test_rows: int = 252,
    step_rows: int | None = None,
    warmup_bars: int = 260,
) -> pd.DataFrame:
    """Ejecuta walk-forward por activo y agrega columna symbol."""
    rows = []
    for symbol, frame in frames.items():
        summary = evaluate_walk_forward(
            frame=frame,
            strategy_specs=strategy_specs,
            config=config,
            train_rows=train_rows,
            test_rows=test_rows,
            step_rows=step_rows,
            warmup_bars=warmup_bars,
        )
        summary.insert(0, "symbol", symbol)
        rows.append(summary)
    if not rows:
        raise ValueError("Se requiere al menos un activo.")
    return pd.concat(rows, ignore_index=True)


def build_robustness_diagnostics(
    train_test: pd.DataFrame,
    walk_forward: pd.DataFrame | None = None,
    min_trades: int = 5,
    large_gap_threshold: float = 0.35,
    suspicious_return: float = 1.0,
    suspicious_sharpe: float = 3.0,
) -> pd.DataFrame:
    """Resume robustez por simbolo/estrategia con score, flags y comentario."""
    if min_trades < 0:
        raise ValueError("min_trades no puede ser negativo.")
    required = {
        "period",
        "strategy",
        "total_return",
        "max_drawdown",
        "number_of_trades",
        "sharpe_ratio",
        "win_rate",
        "vs_buy_and_hold_return",
        "vs_buy_and_hold_drawdown",
    }
    missing = sorted(required - set(train_test.columns))
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    group_columns = ["strategy"]
    if "symbol" in train_test.columns:
        group_columns.insert(0, "symbol")

    rows = []
    for group_key, group in train_test.groupby(group_columns, dropna=False):
        keys = _group_key_dict(group_columns, group_key)
        train = _single_period(group, "train")
        test = _single_period(group, "test")
        if train is None or test is None:
            continue

        wf_stats = _walk_forward_stats(walk_forward, keys) if walk_forward is not None else {}
        flags = _diagnostic_flags(
            train=train,
            test=test,
            wf_stats=wf_stats,
            strategy=str(keys.get("strategy", "")),
            min_trades=min_trades,
            large_gap_threshold=large_gap_threshold,
            suspicious_return=suspicious_return,
            suspicious_sharpe=suspicious_sharpe,
        )
        score = _robustness_score(
            train=train,
            test=test,
            wf_stats=wf_stats,
            flags=flags,
            strategy=str(keys.get("strategy", "")),
            min_trades=min_trades,
        )
        rows.append(
            {
                **keys,
                "train_total_return": train["total_return"],
                "test_total_return": test["total_return"],
                "test_vs_buy_and_hold_return": test["vs_buy_and_hold_return"],
                "train_test_return_gap": float(train["total_return"] - test["total_return"]),
                "abs_train_test_return_gap": abs(float(train["total_return"] - test["total_return"])),
                "test_max_drawdown": test["max_drawdown"],
                "test_vs_buy_and_hold_drawdown": test["vs_buy_and_hold_drawdown"],
                "test_sharpe_ratio": test["sharpe_ratio"],
                "test_win_rate": test["win_rate"],
                "test_number_of_trades": test["number_of_trades"],
                "walk_forward_windows": wf_stats.get("windows", 0),
                "walk_forward_positive_rate": wf_stats.get("positive_rate", math.nan),
                "walk_forward_avg_vs_buy_and_hold": wf_stats.get("average_vs_buy_and_hold", math.nan),
                "robustness_score": score,
                "flags": ";".join(flags),
                "comment": _diagnostic_comment(flags, score),
            }
        )

    diagnostics = pd.DataFrame(rows)
    if diagnostics.empty:
        return diagnostics
    sort_columns = ["robustness_score", "test_vs_buy_and_hold_return", "test_sharpe_ratio"]
    return diagnostics.sort_values(sort_columns, ascending=False).reset_index(drop=True)


def analyze_parameter_sensitivity(
    ranking: pd.DataFrame,
    metric: str = "test_total_return",
    group_column: str = "family",
) -> pd.DataFrame:
    """Resume sensibilidad de una busqueda parametrica por familia/parametro."""
    required = {group_column, "parameters", metric}
    missing = sorted(required - set(ranking.columns))
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    rows = []
    for family, group in ranking.groupby(group_column, dropna=False):
        parsed = []
        for _, row in group.iterrows():
            params = json.loads(row["parameters"]) if isinstance(row["parameters"], str) else dict(row["parameters"])
            parsed.append((params, float(row[metric])))

        parameter_names = sorted({name for params, _ in parsed for name in params})
        for parameter_name in parameter_names:
            values = []
            for params, metric_value in parsed:
                if parameter_name in params:
                    values.append((params[parameter_name], metric_value))
            if not values:
                continue
            unique_values = {str(value) for value, _ in values}
            if len(unique_values) <= 1:
                continue
            metrics = [metric_value for _, metric_value in values]
            best_value, best_metric = max(values, key=lambda item: item[1])
            worst_value, worst_metric = min(values, key=lambda item: item[1])
            rows.append(
                {
                    group_column: family,
                    "parameter": parameter_name,
                    "values_tested": len(unique_values),
                    "metric": metric,
                    "metric_min": worst_metric,
                    "metric_median": float(pd.Series(metrics).median()),
                    "metric_max": best_metric,
                    "metric_range": best_metric - worst_metric,
                    "best_value": best_value,
                    "worst_value": worst_value,
                }
            )
    return pd.DataFrame(rows)


def _single_period(group: pd.DataFrame, period: str) -> pd.Series | None:
    rows = group[group["period"] == period]
    if rows.empty:
        return None
    return rows.iloc[0]


def _walk_forward_stats(walk_forward: pd.DataFrame, keys: dict[str, object]) -> dict[str, float | int]:
    subset = walk_forward
    for column, value in keys.items():
        if column in subset.columns:
            subset = subset[subset[column] == value]
    if subset.empty:
        return {"windows": 0}
    return {
        "windows": int(subset["window"].nunique()) if "window" in subset.columns else int(len(subset)),
        "positive_rate": float((subset["total_return"] > 0).mean()),
        "average_vs_buy_and_hold": float(subset["vs_buy_and_hold_return"].mean()),
        "worst_drawdown": float(subset["max_drawdown"].min()),
    }


def _diagnostic_flags(
    train: pd.Series,
    test: pd.Series,
    wf_stats: dict[str, float | int],
    strategy: str,
    min_trades: int,
    large_gap_threshold: float,
    suspicious_return: float,
    suspicious_sharpe: float,
) -> list[str]:
    if strategy == "buy_and_hold":
        return ["benchmark_reference"]

    flags: list[str] = []
    gap = abs(float(train["total_return"] - test["total_return"]))
    if gap > large_gap_threshold:
        flags.append("large_train_test_gap")
    if float(test["vs_buy_and_hold_return"]) < 0:
        flags.append("underperforms_benchmark_in_test")
    if int(test["number_of_trades"]) < min_trades:
        flags.append("few_trades")
    if float(test["max_drawdown"]) < -0.5:
        flags.append("high_drawdown")

    positive_rate = wf_stats.get("positive_rate")
    if positive_rate is not None and not pd.isna(positive_rate) and float(positive_rate) < 0.5:
        flags.append("unstable_walk_forward")
    avg_vs_benchmark = wf_stats.get("average_vs_buy_and_hold")
    if avg_vs_benchmark is not None and not pd.isna(avg_vs_benchmark) and float(avg_vs_benchmark) < 0:
        flags.append("walk_forward_underperforms_benchmark")

    win_rate = float(test["win_rate"]) if not pd.isna(test["win_rate"]) else math.nan
    if (
        float(test["total_return"]) >= suspicious_return
        and int(test["number_of_trades"]) < min_trades
    ) or float(test["sharpe_ratio"]) >= suspicious_sharpe or (
        not math.isnan(win_rate) and win_rate >= 0.9 and int(test["number_of_trades"]) < 10
    ):
        flags.append("too_good_to_trust")
    return flags


def _robustness_score(
    train: pd.Series,
    test: pd.Series,
    wf_stats: dict[str, float | int],
    flags: list[str],
    strategy: str,
    min_trades: int,
) -> float:
    if strategy == "buy_and_hold":
        return 100.0

    score = 100.0
    gap = abs(float(train["total_return"] - test["total_return"]))
    score -= min(gap * 100, 35)

    vs_benchmark = float(test["vs_buy_and_hold_return"])
    if vs_benchmark < 0:
        score -= min(abs(vs_benchmark) * 100, 30)

    trades = int(test["number_of_trades"])
    if trades < min_trades:
        score -= 20 * (1 - trades / max(min_trades, 1))

    positive_rate = wf_stats.get("positive_rate")
    if positive_rate is not None and not pd.isna(positive_rate):
        score -= max(0.0, 0.5 - float(positive_rate)) * 30

    avg_vs_benchmark = wf_stats.get("average_vs_buy_and_hold")
    if avg_vs_benchmark is not None and not pd.isna(avg_vs_benchmark) and float(avg_vs_benchmark) < 0:
        score -= min(abs(float(avg_vs_benchmark)) * 50, 15)

    if "too_good_to_trust" in flags:
        score -= 25
    if "high_drawdown" in flags:
        score -= 15
    return round(max(0.0, min(100.0, score)), 2)


def _diagnostic_comment(flags: list[str], score: float) -> str:
    if "benchmark_reference" in flags:
        return "Benchmark de referencia; no se interpreta como estrategia optimizada."
    if "too_good_to_trust" in flags:
        return "Resultado demasiado llamativo; revisar datos, trades y robustez antes de creerlo."
    if "underperforms_benchmark_in_test" in flags and "few_trades" in flags:
        return "Debil: pierde contra benchmark en test y tiene pocos trades."
    if "large_train_test_gap" in flags:
        return "Inestable: hay brecha grande entre train y test."
    if "unstable_walk_forward" in flags:
        return "Inestable: falla en demasiadas ventanas walk-forward."
    if score >= 75:
        return "Razonable para investigar mas; no implica aptitud para operar real."
    if score >= 50:
        return "Mixto: requiere mas pruebas antes de confiar."
    return "Fragil: mejor descartarla o redisenarla."


def _group_key_dict(columns: list[str], group_key: object) -> dict[str, object]:
    if len(columns) == 1:
        return {columns[0]: group_key}
    return dict(zip(columns, group_key, strict=True))
