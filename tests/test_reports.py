from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from algotrading.backtesting import BacktestConfig, run_backtest
from algotrading.reports import (
    build_exposure_summary,
    build_period_extremes,
    build_report_comment,
    calculate_monthly_returns,
    generate_backtest_report,
)


def _frame(prices, signals):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
            "adj_close": prices,
            "signal": signals,
        }
    )


def _sandbox():
    path = Path("tests/.tmp/report_tests") / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


def _result():
    return run_backtest(
        _frame([100, 110, 120, 130, 125, 140, 150], [1, 1, 1, 0, 0, 1, 1]),
        config=BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )


def test_calculate_monthly_returns_returns_month_rows():
    result = run_backtest(
        pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01"]),
                "adj_close": [100, 110, 121],
                "signal": [1, 1, 1],
            }
        ),
        config=BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )

    monthly = calculate_monthly_returns(result.equity_curve)

    assert monthly["month"].tolist() == ["2024-01", "2024-02"]
    assert monthly.loc[0, "monthly_return"] == pytest.approx(0.0)
    assert monthly.loc[1, "monthly_return"] == pytest.approx(0.10)


def test_build_period_extremes_finds_best_and_worst_windows():
    result = _result()

    extremes = build_period_extremes(result.equity_curve, window=2, top_n=2)

    assert set(extremes["kind"]) == {"best", "worst"}
    assert len(extremes) == 4
    assert extremes[extremes["kind"] == "best"]["return"].max() > 0


def test_build_exposure_summary_uses_position_column():
    result = _result()

    exposure = build_exposure_summary(result.equity_curve)

    assert exposure.loc[0, "total_bars"] == len(result.equity_curve)
    assert 0 < exposure.loc[0, "exposure_ratio"] <= 1


def test_build_report_comment_flags_small_trade_sample():
    result = _result()
    exposure = build_exposure_summary(result.equity_curve)

    comment = build_report_comment(result.metrics, exposure)

    assert "benchmark" in comment
    assert "muestra de trades es chica" in comment


def test_generate_backtest_report_writes_expected_artifacts():
    result = _result()
    output_dir = _sandbox()

    artifacts = generate_backtest_report(
        result=result,
        output_dir=output_dir,
        symbol="SPY",
        strategy_name="test_strategy",
        window=2,
        top_n=2,
    )

    assert artifacts.report_path.exists()
    assert artifacts.metrics_table_path.exists()
    assert artifacts.monthly_returns_path.exists()
    assert artifacts.period_extremes_path.exists()
    assert artifacts.exposure_path.exists()
    assert artifacts.figure_path.exists()
    assert artifacts.interactive_figure_path.exists()
    report = artifacts.report_path.read_text(encoding="utf-8")
    assert "Comentario automatico" in report
    assert "Retornos mensuales" in report
    assert "equity_drawdown.html" in report
