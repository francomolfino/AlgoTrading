from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from algotrading.backtesting import BacktestConfig, BacktestResult, run_backtest
from algotrading.strategies.registry import StrategySpec


@dataclass(frozen=True)
class IndexSplit:
    name: str
    start_index: int
    end_index: int


@dataclass(frozen=True)
class WalkForwardSplit:
    window: int
    train_start_index: int
    train_end_index: int
    test_start_index: int
    test_end_index: int


def make_train_test_split(frame: pd.DataFrame, train_ratio: float = 0.7) -> tuple[IndexSplit, IndexSplit]:
    if not 0.1 <= train_ratio <= 0.9:
        raise ValueError("train_ratio debe estar entre 0.1 y 0.9.")
    if len(frame) < 4:
        raise ValueError("Se necesitan al menos 4 filas para separar train/test.")

    split_index = int(len(frame) * train_ratio)
    split_index = min(max(split_index, 2), len(frame) - 2)
    return (
        IndexSplit("train", 0, split_index),
        IndexSplit("test", split_index, len(frame)),
    )


def make_walk_forward_splits(
    frame: pd.DataFrame,
    train_rows: int = 756,
    test_rows: int = 252,
    step_rows: int | None = None,
) -> list[WalkForwardSplit]:
    if train_rows < 2:
        raise ValueError("train_rows debe ser al menos 2.")
    if test_rows < 2:
        raise ValueError("test_rows debe ser al menos 2.")
    step_rows = step_rows or test_rows
    if step_rows <= 0:
        raise ValueError("step_rows debe ser mayor a cero.")
    if len(frame) < train_rows + test_rows:
        raise ValueError("No hay suficientes filas para walk-forward.")

    splits: list[WalkForwardSplit] = []
    start = 0
    window = 1
    while start + train_rows + test_rows <= len(frame):
        train_end = start + train_rows
        test_end = train_end + test_rows
        splits.append(
            WalkForwardSplit(
                window=window,
                train_start_index=start,
                train_end_index=train_end,
                test_start_index=train_end,
                test_end_index=test_end,
            )
        )
        start += step_rows
        window += 1
    return splits


def evaluate_train_test(
    frame: pd.DataFrame,
    strategy_specs: list[StrategySpec],
    config: BacktestConfig,
    train_ratio: float = 0.7,
    warmup_bars: int = 260,
) -> pd.DataFrame:
    data = _prepare_frame(frame)
    splits = make_train_test_split(data, train_ratio=train_ratio)
    rows = []
    for split in splits:
        for spec in strategy_specs:
            result = _run_strategy_for_index_range(
                frame=data,
                spec=spec,
                config=config,
                start_index=split.start_index,
                end_index=split.end_index,
                warmup_bars=warmup_bars,
            )
            rows.append(_summary_row(spec.name, split.name, result))
    return _with_benchmark_columns(pd.DataFrame(rows), group_columns=["period"])


def evaluate_walk_forward(
    frame: pd.DataFrame,
    strategy_specs: list[StrategySpec],
    config: BacktestConfig,
    train_rows: int = 756,
    test_rows: int = 252,
    step_rows: int | None = None,
    warmup_bars: int = 260,
) -> pd.DataFrame:
    data = _prepare_frame(frame)
    splits = make_walk_forward_splits(
        data,
        train_rows=train_rows,
        test_rows=test_rows,
        step_rows=step_rows,
    )
    rows = []
    for split in splits:
        for spec in strategy_specs:
            result = _run_strategy_for_index_range(
                frame=data,
                spec=spec,
                config=config,
                start_index=split.test_start_index,
                end_index=split.test_end_index,
                warmup_bars=max(warmup_bars, train_rows),
            )
            row = _summary_row(spec.name, "walk_forward_test", result)
            row.update(
                {
                    "window": split.window,
                    "train_start": data.loc[split.train_start_index, "date"].strftime("%Y-%m-%d"),
                    "train_end": data.loc[split.train_end_index - 1, "date"].strftime("%Y-%m-%d"),
                    "test_start": data.loc[split.test_start_index, "date"].strftime("%Y-%m-%d"),
                    "test_end": data.loc[split.test_end_index - 1, "date"].strftime("%Y-%m-%d"),
                }
            )
            rows.append(row)
    return _with_benchmark_columns(pd.DataFrame(rows), group_columns=["window", "period"])


def _run_strategy_for_index_range(
    frame: pd.DataFrame,
    spec: StrategySpec,
    config: BacktestConfig,
    start_index: int,
    end_index: int,
    warmup_bars: int,
) -> BacktestResult:
    if end_index - start_index < 2:
        raise ValueError("Cada periodo debe tener al menos dos filas.")
    warmup_start = max(0, start_index - max(0, warmup_bars))
    subset = frame.iloc[warmup_start:end_index].reset_index(drop=True)
    signal_frame = spec.function(subset, signal_column=config.signal_column, **spec.parameters)
    period_start = start_index - warmup_start
    period_frame = signal_frame.iloc[period_start:].reset_index(drop=True)
    return run_backtest(period_frame, config=config)


def _summary_row(
    strategy: str,
    period: str,
    result: BacktestResult,
) -> dict[str, float | int | str]:
    metrics = result.metrics
    equity_curve = result.equity_curve
    return {
        "period": period,
        "strategy": strategy,
        "start_date": equity_curve["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": equity_curve["date"].iloc[-1].strftime("%Y-%m-%d"),
        "rows": int(len(equity_curve)),
        "final_equity": metrics["final_equity"],
        "total_return": metrics["total_return"],
        "cagr": metrics["cagr"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "max_drawdown": metrics["max_drawdown"],
        "win_rate": metrics["win_rate"],
        "number_of_trades": metrics["number_of_trades"],
        "total_commissions": metrics["total_commissions"],
    }


def _with_benchmark_columns(summary: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    benchmark = summary[summary["strategy"] == "buy_and_hold"][
        group_columns + ["total_return", "max_drawdown"]
    ].rename(
        columns={
            "total_return": "buy_and_hold_return",
            "max_drawdown": "buy_and_hold_max_drawdown",
        }
    )
    merged = summary.merge(benchmark, on=group_columns, how="left")
    merged["vs_buy_and_hold_return"] = (
        merged["total_return"] - merged["buy_and_hold_return"]
    )
    merged["vs_buy_and_hold_drawdown"] = (
        merged["max_drawdown"] - merged["buy_and_hold_max_drawdown"]
    )
    return merged


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = ["date"]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    if data["date"].isna().any():
        raise ValueError("Hay fechas invalidas.")
    return data.sort_values("date").reset_index(drop=True)
