import pandas as pd
import pytest

from algotrading.backtesting import BacktestConfig, run_backtest
from algotrading.data.schema import normalize_ohlcv_dataframe
from algotrading.strategies import generate_sma_crossover_signals


def test_normalized_data_strategy_and_backtest_flow_is_consistent():
    raw = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=6, freq="D"),
            "Open": [100, 101, 102, 103, 104, 105],
            "High": [101, 102, 103, 104, 105, 106],
            "Low": [99, 100, 101, 102, 103, 104],
            "Close": [100, 101, 102, 103, 104, 105],
            "Adj Close": [100, 101, 102, 103, 104, 105],
            "Volume": [1_000] * 6,
        }
    ).sort_values("Date", ascending=False)

    normalized = normalize_ohlcv_dataframe(raw)
    signals = generate_sma_crossover_signals(normalized, fast_window=2, slow_window=3)
    result = run_backtest(
        signals,
        config=BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )

    assert normalized["date"].is_monotonic_increasing
    assert signals["signal"].tolist() == [0, 0, 1, 1, 1, 1]
    assert len(result.equity_curve) == len(normalized)
    assert result.equity_curve.loc[2, "position"] == 0
    assert result.equity_curve.loc[3, "action"] == "buy"
    assert result.trades.loc[0, "entry_price"] == pytest.approx(103)
    assert result.trades.loc[0, "exit_reason"] == "end_of_backtest"
    assert result.metrics["number_of_trades"] == 1
