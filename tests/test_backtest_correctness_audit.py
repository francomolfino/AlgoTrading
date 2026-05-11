from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from algotrading.backtesting import BacktestConfig, run_backtest, run_backtest_correctness_audit


def _frame(prices, signals):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
            "adj_close": prices,
            "signal": signals,
        }
    )


def test_backtest_correctness_audit_passes_and_writes_report():
    output_dir = Path("tests/.tmp/backtest_correctness")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{uuid4().hex}_backtest_correctness_audit.md"

    result = run_backtest_correctness_audit(report_path=report_path)

    assert result.passed
    assert len(result.checks) == 10
    assert {check.category for check in result.checks} >= {
        "lookahead bias",
        "comisiones/slippage/pnl",
        "cash/equity/drawdown",
        "benchmark",
    }
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "Backtest Correctness Audit" in report
    assert "Senal en t ejecuta en t+1" in report
    assert "Limitaciones conocidas" in report


def test_golden_trade_with_costs_matches_manual_formula():
    initial_capital = 1_000.0
    commission_rate = 0.01
    slippage_rate = 0.01
    entry_mark = 100.0
    exit_mark = 110.0
    entry_execution = entry_mark * (1 + slippage_rate)
    exit_execution = exit_mark * (1 - slippage_rate)
    entry_notional = initial_capital / (1 + commission_rate)
    entry_commission = entry_notional * commission_rate
    shares = entry_notional / entry_execution
    exit_notional = shares * exit_execution
    exit_commission = exit_notional * commission_rate
    expected_final = exit_notional - exit_commission
    expected_pnl = expected_final - initial_capital

    result = run_backtest(
        _frame([100, 100, 110, 110], [1, 1, 0, 0]),
        BacktestConfig(initial_capital=initial_capital, commission_bps=100, slippage_bps=100),
    )

    assert result.metrics["final_equity"] == pytest.approx(expected_final)
    assert result.trades.loc[0, "pnl"] == pytest.approx(expected_pnl)
    assert result.trades.loc[0, "entry_price"] == pytest.approx(entry_execution)
    assert result.trades.loc[0, "exit_price"] == pytest.approx(exit_execution)
    assert result.orders.loc[0, "commission"] == pytest.approx(entry_commission)
    assert result.orders.loc[1, "commission"] == pytest.approx(exit_commission)


def test_golden_signal_delay_prevents_same_bar_execution():
    result = run_backtest(
        _frame([100, 150, 90, 90], [0, 1, 0, 0]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )

    assert result.equity_curve.loc[1, "raw_signal"] == 1
    assert result.equity_curve.loc[1, "action"] == ""
    assert result.equity_curve.loc[2, "action"] == "buy"
    assert result.trades.loc[0, "entry_date"] == pd.Timestamp("2024-01-03")
    assert result.trades.loc[0, "entry_price"] == pytest.approx(90)


def test_golden_gap_stop_loss_exits_at_observed_bar_price():
    result = run_backtest(
        _frame([100, 100, 70, 80], [1, 1, 1, 1]),
        BacktestConfig(
            initial_capital=1_000,
            commission_bps=0,
            slippage_bps=0,
            stop_loss_pct=0.10,
        ),
    )

    assert result.trades.loc[0, "exit_reason"] == "stop_loss"
    assert result.trades.loc[0, "exit_date"] == pd.Timestamp("2024-01-03")
    assert result.trades.loc[0, "exit_price"] == pytest.approx(70)
    assert result.metrics["final_equity"] == pytest.approx(700)


def test_golden_cash_and_position_accounting_are_consistent():
    result = run_backtest(
        _frame([100, 100, 80, 120, 90], [1, 1, 1, 0, 0]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    equity = result.equity_curve

    assert (equity["position"].isin([0, 1])).all()
    assert (equity["shares"] >= 0).all()
    assert (equity["cash"] >= 0).all()
    assert equity["equity"].tolist() == pytest.approx(
        (equity["cash"] + equity["shares"] * equity["price"]).tolist()
    )
    assert equity["drawdown"].tolist() == pytest.approx(
        (equity["equity"] / equity["equity"].cummax() - 1).tolist()
    )
