import pandas as pd
import pytest

from algotrading.metrics import calculate_drawdown
from algotrading.portfolio import (
    build_price_matrix,
    calculate_return_matrix,
    run_equal_weight_portfolio,
    simulate_equal_weight_rebalancing,
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
    assert not result.portfolio_orders.empty


def test_simulate_equal_weight_rebalancing_records_orders_and_weights():
    prices = pd.DataFrame(
        {"AAA": [100, 200], "BBB": [100, 100]},
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )

    equity, orders = simulate_equal_weight_rebalancing(
        prices,
        initial_capital=1_000,
        rebalance_frequency="none",
    )

    assert orders["side"].tolist() == ["buy", "buy"]
    assert equity.loc[0, "weight_AAA"] == pytest.approx(0.5)
    assert equity.loc[1, "equity"] == pytest.approx(1_500)
    assert equity.loc[1, "weight_AAA"] == pytest.approx(2 / 3)


def test_rebalanced_portfolio_with_costs_lags_no_cost_version():
    frames = {
        "AAA": _frame("2024-01-01", [100, 120, 100, 120]),
        "BBB": _frame("2024-01-01", [100, 80, 100, 80]),
    }

    no_cost = run_equal_weight_portfolio(
        frames,
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
    )
    with_costs = run_equal_weight_portfolio(
        frames,
        initial_capital=1_000,
        commission_bps=10,
        slippage_bps=10,
    )

    assert with_costs.portfolio_equity["equity"].iloc[-1] < no_cost.portfolio_equity["equity"].iloc[-1]
    assert with_costs.portfolio_orders["commission"].sum() > 0
    first_buy = with_costs.portfolio_orders[with_costs.portfolio_orders["side"] == "buy"].iloc[0]
    assert first_buy["execution_price"] > first_buy["mark_price"]


def test_rebalanced_portfolio_rejects_invalid_frequency():
    prices = pd.DataFrame(
        {"AAA": [100, 101], "BBB": [100, 101]},
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )

    with pytest.raises(ValueError, match="rebalance_frequency"):
        simulate_equal_weight_rebalancing(prices, rebalance_frequency="hourly")
