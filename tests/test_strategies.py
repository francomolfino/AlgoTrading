import pandas as pd
import pytest

from algotrading.strategies import (
    build_default_strategy_specs,
    calculate_rsi,
    generate_breakout_signals,
    generate_buy_and_hold_signals,
    generate_rsi_signals,
    generate_sma_crossover_signals,
    generate_trend_filter_signals,
)


def _frame(prices):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
            "adj_close": prices,
        }
    )


def test_buy_and_hold_signal_is_always_one():
    result = generate_buy_and_hold_signals(_frame([10, 11, 12]))

    assert result["signal"].tolist() == [1, 1, 1]


def test_sma_crossover_waits_until_slow_average_exists():
    result = generate_sma_crossover_signals(
        _frame([10, 11, 12, 13, 14]),
        fast_window=2,
        slow_window=3,
    )

    assert result["signal"].tolist() == [0, 0, 1, 1, 1]


def test_sma_crossover_rejects_invalid_windows():
    with pytest.raises(ValueError, match="menor"):
        generate_sma_crossover_signals(_frame([10, 11, 12]), fast_window=3, slow_window=2)


def test_rsi_calculation_returns_high_value_for_persistent_gains():
    rsi = calculate_rsi(pd.Series([10, 11, 12, 13]), window=2)

    assert rsi.iloc[-1] == pytest.approx(100)


def test_rsi_strategy_enters_oversold_and_exits_overbought():
    result = generate_rsi_signals(
        _frame([10, 9, 8, 9, 10, 11]),
        window=2,
        oversold=30,
        overbought=70,
    )

    assert result["signal"].tolist() == [0, 0, 1, 1, 0, 0]


def test_breakout_strategy_uses_previous_high_and_previous_low():
    result = generate_breakout_signals(
        _frame([10, 11, 12, 13, 12, 11, 10]),
        entry_window=2,
        exit_window=2,
    )

    assert result["signal"].tolist() == [0, 0, 1, 1, 1, 0, 0]


def test_trend_filter_requires_cross_and_long_trend():
    result = generate_trend_filter_signals(
        _frame([10, 11, 12, 13, 14, 15]),
        fast_window=2,
        slow_window=3,
        trend_window=4,
    )

    assert result["signal"].tolist() == [0, 0, 0, 1, 1, 1]


def test_default_strategy_specs_always_start_with_buy_and_hold_benchmark():
    specs = build_default_strategy_specs()

    assert specs[0].name == "buy_and_hold"
    assert [spec.name for spec in specs] == [
        "buy_and_hold",
        "sma_cross_50_200",
        "rsi_14_30_70",
        "breakout_55_20",
        "trend_filter_20_100_200",
    ]
