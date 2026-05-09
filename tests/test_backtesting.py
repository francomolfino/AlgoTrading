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
    assert result.orders.empty
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
    assert result.orders["side"].tolist() == ["buy", "sell"]
    assert result.orders["status"].tolist() == ["filled", "filled"]


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


def test_position_fraction_keeps_cash_and_scales_exposure():
    frame = _frame([100, 110, 120, 130], [1, 1, 0, 0])
    config = BacktestConfig(
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
        position_fraction=0.5,
    )

    result = run_backtest(frame, config=config)

    assert result.equity_curve.loc[1, "action"] == "buy"
    assert result.equity_curve.loc[1, "cash"] == pytest.approx(500.0)
    assert result.equity_curve.loc[1, "target_exposure"] == pytest.approx(0.5)
    assert result.metrics["final_equity"] == pytest.approx(500 + (500 / 110) * 130)


def test_stop_loss_closes_position_and_records_reason():
    frame = _frame([100, 100, 89, 90], [1, 0, 0, 0])
    config = BacktestConfig(
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
        stop_loss_pct=0.10,
    )

    result = run_backtest(frame, config=config)

    assert result.trades.loc[0, "exit_reason"] == "stop_loss"
    assert result.trades.loc[0, "exit_date"] == pd.Timestamp("2024-01-03")
    assert result.orders.loc[1, "reason"] == "stop_loss"


def test_take_profit_closes_position_and_records_reason():
    frame = _frame([100, 100, 126, 126], [1, 1, 1, 1])
    config = BacktestConfig(
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
        take_profit_pct=0.25,
    )

    result = run_backtest(frame, config=config)

    assert result.trades.loc[0, "exit_reason"] == "take_profit"
    assert result.orders.loc[1, "reason"] == "take_profit"


def test_max_drawdown_halts_strategy_and_liquidates_position():
    frame = _frame([100, 100, 80, 120, 130], [1, 1, 1, 1, 1])
    config = BacktestConfig(
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
        max_drawdown_pct=0.10,
    )

    result = run_backtest(frame, config=config)

    assert result.trades.loc[0, "exit_reason"] == "max_drawdown"
    assert result.equity_curve["risk_halted"].any()
    assert result.equity_curve.loc[3, "position"] == 0
    assert result.metrics["risk_halt_triggered"] == 1


def test_max_trades_per_day_can_block_entries():
    frame = _frame([100, 110, 120], [1, 1, 1])
    config = BacktestConfig(max_trades_per_day=0)

    result = run_backtest(frame, config=config)

    assert result.orders.empty
    assert result.equity_curve.loc[1, "blocked_reason"] == "trade_limit"


def test_volatility_target_reduces_position_fraction_when_volatility_is_high():
    frame = _frame([100, 120, 90, 130, 140, 150], [0, 0, 0, 1, 1, 0])
    config = BacktestConfig(
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
        volatility_target_pct=0.10,
        volatility_window=2,
    )

    result = run_backtest(frame, config=config)

    assert result.equity_curve.loc[4, "action"] == "buy"
    assert 0 < result.equity_curve.loc[4, "target_exposure"] < 1


def test_backtest_adds_buy_and_hold_benchmark_metrics():
    frame = _frame([100, 110, 120, 130], [0, 0, 0, 0])
    config = BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0)

    result = run_backtest(frame, config=config)

    assert "benchmark_equity" in result.equity_curve.columns
    assert result.metrics["benchmark_total_return"] == pytest.approx(130 / 110 - 1)
    assert result.metrics["excess_return_vs_benchmark"] == pytest.approx(-(130 / 110 - 1))


def test_backtest_rejects_non_binary_signals_for_now():
    frame = _frame([100, 110, 120], [0, -1, 1])

    with pytest.raises(ValueError, match="0/1"):
        run_backtest(frame)


def test_backtest_rejects_missing_signals_by_default():
    frame = _frame([100, 110, 120], [0, None, 1])

    with pytest.raises(ValueError, match="senales faltantes"):
        run_backtest(frame)


def test_backtest_can_treat_missing_signals_as_cash_when_explicit():
    frame = _frame([100, 110, 120], [1, None, 0])
    config = BacktestConfig(
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
        allow_missing_signals=True,
    )

    result = run_backtest(frame, config=config)

    assert result.equity_curve.loc[1, "action"] == "buy"
    assert result.equity_curve.loc[2, "action"] == "sell"
    assert result.metrics["number_of_trades"] == 1


def test_backtest_rejects_duplicated_dates():
    frame = _frame([100, 110, 120], [0, 1, 0])
    frame.loc[2, "date"] = frame.loc[1, "date"]

    with pytest.raises(ValueError, match="duplicadas"):
        run_backtest(frame)


def test_backtest_rejects_invalid_risk_config():
    with pytest.raises(ValueError, match="position_fraction"):
        run_backtest(_frame([100, 110], [0, 0]), BacktestConfig(position_fraction=0))
    with pytest.raises(ValueError, match="stop_loss_pct"):
        run_backtest(_frame([100, 110], [0, 0]), BacktestConfig(stop_loss_pct=1))
    with pytest.raises(ValueError, match="take_profit_pct"):
        run_backtest(_frame([100, 110], [0, 0]), BacktestConfig(take_profit_pct=0))
    with pytest.raises(ValueError, match="max_drawdown_pct"):
        run_backtest(_frame([100, 110], [0, 0]), BacktestConfig(max_drawdown_pct=1))
    with pytest.raises(ValueError, match="volatility_target_pct"):
        run_backtest(_frame([100, 110], [0, 0]), BacktestConfig(volatility_target_pct=0))


def test_backtest_marks_open_position_to_market_when_not_forced_closed():
    frame = _frame([100, 110, 120], [1, 1, 1])
    config = BacktestConfig(
        initial_capital=1_000,
        commission_bps=0,
        slippage_bps=0,
        close_open_position=False,
    )

    result = run_backtest(frame, config=config)

    assert result.metrics["number_of_trades"] == 0
    assert result.equity_curve.loc[1, "action"] == "buy"
    assert result.equity_curve.loc[2, "position"] == 1
    assert result.metrics["final_equity"] == pytest.approx(1_000 * 120 / 110)


def test_backtest_forced_close_marks_exit_reason_end_of_backtest():
    frame = _frame([100, 110, 120], [1, 1, 1])
    config = BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0)

    result = run_backtest(frame, config=config)

    assert result.metrics["number_of_trades"] == 1
    assert result.trades.loc[0, "exit_reason"] == "end_of_backtest"
    assert result.trades.loc[0, "exit_date"] == pd.Timestamp("2024-01-03")
