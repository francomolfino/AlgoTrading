import pandas as pd
import pytest

from algotrading.backtesting import BacktestConfig
from algotrading.optimization import (
    build_rsi_candidates,
    build_sma_candidates,
    run_controlled_search,
    validate_candidate_count,
)


def _frame(rows=80):
    prices = []
    price = 100.0
    for index in range(rows):
        price += 1.0 if index < rows * 0.7 else -0.5
        prices.append(price)
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "adj_close": prices,
        }
    )


def test_build_sma_candidates_keeps_only_fast_below_slow():
    candidates = build_sma_candidates(fast_windows=[5, 20], slow_windows=[10])

    assert [candidate.spec.name for candidate in candidates] == ["sma_cross_5_10"]


def test_build_rsi_candidates_uses_threshold_pairs():
    candidates = build_rsi_candidates(
        windows=[14],
        threshold_pairs=[(30, 70), (25, 75)],
    )

    assert [candidate.spec.name for candidate in candidates] == [
        "rsi_14_30_70",
        "rsi_14_25_75",
    ]


def test_validate_candidate_count_rejects_large_searches():
    candidates = build_sma_candidates(
        fast_windows=[5, 10, 15],
        slow_windows=[20, 30],
    )

    assert validate_candidate_count(candidates, max_combinations=6) == 6
    with pytest.raises(ValueError, match="Demasiadas combinaciones"):
        validate_candidate_count(candidates, max_combinations=5)


def test_run_controlled_search_returns_ranked_candidates_and_period_details():
    candidates = build_sma_candidates(fast_windows=[3, 5], slow_windows=[10])

    result = run_controlled_search(
        frame=_frame(),
        candidates=candidates,
        config=BacktestConfig(commission_bps=0, slippage_bps=0),
        train_ratio=0.7,
        warmup_bars=15,
        max_combinations=5,
    )

    assert list(result.ranking["rank"]) == [1, 2]
    assert "test_vs_buy_and_hold_return" in result.ranking.columns
    assert "abs_train_test_return_gap" in result.ranking.columns
    assert set(result.period_results["period"]) == {"train", "test"}
    assert "buy_and_hold" in set(result.period_results["strategy"])
