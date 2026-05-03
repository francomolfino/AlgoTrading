import math

import pandas as pd
import pytest

from algotrading.backtesting import BacktestConfig, run_backtest


def _frame(prices, signals):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
            "adj_close": prices,
            "signal": signals,
        }
    )


def test_backtest_stays_in_cash_when_signal_is_zero():
    result = run_backtest(_frame([100, 110, 120], [0, 0, 0]))

    assert result.metrics["final_equity"] == pytest.approx(10_000.0)
    assert result.metrics["total_return"] == pytest.approx(0.0)
    assert result.metrics["number_of_trades"] == 0
    assert math.isnan(result.metrics["win_rate"])


def test_backtest_executes_signal_on_next_bar_to_avoid_lookahead():
    frame = _frame([100, 200, 200], [1, 0, 0])
    config = BacktestConfig(commission_bps=0, slippage_bps=0)

    result = run_backtest(frame, config=config)

    assert result.equity_curve.loc[0, "position"] == 0
    assert result.equity_curve.loc[1, "action"] == "buy"
    assert result.metrics["total_return"] == pytest.approx(0.0)


def test_backtest_calculates_trade_pnl_without_costs():
    frame = _frame([100, 110, 120, 130], [1, 1, 0, 0])
    config = BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0)

    result = run_backtest(frame, config=config)

    assert result.metrics["number_of_trades"] == 1
    assert result.metrics["win_rate"] == pytest.approx(1.0)
    assert result.metrics["final_equity"] == pytest.approx(1_000 * 130 / 110)
    assert result.trades.loc[0, "return_pct"] == pytest.approx(130 / 110 - 1)


def test_commissions_and_slippage_reduce_final_equity():
    frame = _frame([100, 110, 120, 130], [1, 1, 0, 0])
    no_costs = run_backtest(
        frame,
        config=BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    with_costs = run_backtest(
        frame,
        config=BacktestConfig(initial_capital=1_000, commission_bps=10, slippage_bps=10),
    )

    assert with_costs.metrics["final_equity"] < no_costs.metrics["final_equity"]


def test_backtest_rejects_non_binary_signals_for_now():
    frame = _frame([100, 110, 120], [0, -1, 1])

    with pytest.raises(ValueError, match="0/1"):
        run_backtest(frame)
