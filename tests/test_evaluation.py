import pandas as pd
import pytest

from algotrading.backtesting import BacktestConfig
from algotrading.evaluation import (
    count_parameter_combinations,
    evaluate_train_test,
    evaluate_walk_forward,
    make_train_test_split,
    make_walk_forward_splits,
    validate_parameter_grid_size,
)
from algotrading.strategies.registry import StrategySpec


def _frame(rows=20):
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "adj_close": [100 + index for index in range(rows)],
        }
    )


def _always_long(frame, signal_column="signal"):
    result = frame.copy()
    result[signal_column] = 1
    return result


def _always_cash(frame, signal_column="signal"):
    result = frame.copy()
    result[signal_column] = 0
    return result


def _specs():
    return [
        StrategySpec("buy_and_hold", _always_long, {}),
        StrategySpec("cash", _always_cash, {}),
    ]


def test_make_train_test_split_respects_order_and_minimum_rows():
    train, test = make_train_test_split(_frame(10), train_ratio=0.6)

    assert train.name == "train"
    assert test.name == "test"
    assert train.start_index == 0
    assert train.end_index == 6
    assert test.start_index == 6
    assert test.end_index == 10


def test_evaluate_train_test_adds_buy_and_hold_benchmark_columns():
    summary = evaluate_train_test(
        frame=_frame(12),
        strategy_specs=_specs(),
        config=BacktestConfig(commission_bps=0, slippage_bps=0),
        train_ratio=0.5,
        warmup_bars=2,
    )

    assert set(summary["period"]) == {"train", "test"}
    assert "vs_buy_and_hold_return" in summary.columns
    cash_rows = summary[summary["strategy"] == "cash"]
    assert (cash_rows["vs_buy_and_hold_return"] < 0).all()


def test_make_walk_forward_splits_uses_rolling_windows():
    splits = make_walk_forward_splits(
        _frame(12),
        train_rows=4,
        test_rows=3,
        step_rows=3,
    )

    assert len(splits) == 2
    assert splits[0].train_start_index == 0
    assert splits[0].test_start_index == 4
    assert splits[1].train_start_index == 3
    assert splits[1].test_start_index == 7


def test_evaluate_walk_forward_returns_test_rows_only():
    summary = evaluate_walk_forward(
        frame=_frame(12),
        strategy_specs=_specs(),
        config=BacktestConfig(commission_bps=0, slippage_bps=0),
        train_rows=4,
        test_rows=3,
        step_rows=3,
        warmup_bars=2,
    )

    assert set(summary["period"]) == {"walk_forward_test"}
    assert set(summary["window"]) == {1, 2}
    assert len(summary) == 4


def test_parameter_grid_guard_counts_and_rejects_large_searches():
    grid = {"fast": [10, 20, 30], "slow": [50, 100]}

    assert count_parameter_combinations(grid) == 6
    assert validate_parameter_grid_size(grid, max_combinations=6) == 6

    with pytest.raises(ValueError, match="Grid demasiado grande"):
        validate_parameter_grid_size(grid, max_combinations=5)
