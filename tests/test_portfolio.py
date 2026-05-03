import pandas as pd
import pytest

from algotrading.portfolio import (
    build_price_matrix,
    calculate_drawdown,
    calculate_return_matrix,
    run_equal_weight_portfolio,
)


def _frame(start, prices):
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=len(prices), freq="D"),
            "adj_close": prices,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [100] * len(prices),
        }
    )


def test_build_price_matrix_aligns_common_dates_only():
    frames = {
        "AAA": _frame("2024-01-01", [10, 11, 12]),
        "BBB": _frame("2024-01-02", [20, 22, 24]),
    }

    prices = build_price_matrix(frames)

    assert prices.index.tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
    assert prices["AAA"].tolist() == [11, 12]
    assert prices["BBB"].tolist() == [20, 22]


def test_calculate_return_matrix_uses_simple_returns():
    prices = pd.DataFrame(
        {"AAA": [100, 110, 121], "BBB": [100, 90, 99]},
        index=pd.date_range("2024-01-01", periods=3, freq="D"),
    )

    returns = calculate_return_matrix(prices)

    assert returns["AAA"].tolist() == pytest.approx([0.10, 0.10])
    assert returns["BBB"].tolist() == pytest.approx([-0.10, 0.10])


def test_calculate_drawdown_returns_peak_to_trough_declines():
    drawdown = calculate_drawdown(pd.Series([100, 120, 90, 150]))

    assert drawdown.tolist() == pytest.approx([0.0, 0.0, -0.25, 0.0])


def test_run_equal_weight_portfolio_builds_summary_and_correlations():
    frames = {
        "AAA": _frame("2024-01-01", [100, 110, 121, 133.1]),
        "BBB": _frame("2024-01-01", [100, 90, 99, 108.9]),
    }

    result = run_equal_weight_portfolio(frames, initial_capital=1_000)

    assert list(result.price_matrix.columns) == ["AAA", "BBB"]
    assert result.correlations.shape == (2, 2)
    assert set(result.summary["name"]) == {"AAA", "BBB", "equal_weight_portfolio"}
    assert result.portfolio_equity["equity"].iloc[0] == pytest.approx(1_000)
    assert result.portfolio_equity["equity"].iloc[-1] == pytest.approx(1_210)
