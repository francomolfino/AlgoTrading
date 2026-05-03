import math

import pandas as pd
import pytest

from algotrading.analysis.exploration import (
    add_daily_returns,
    add_moving_averages,
    prepare_exploration_frame,
    summarize_exploration,
)


def _sample_frame():
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "open": [10, 11, 12, 13, 14],
            "high": [11, 12, 13, 14, 15],
            "low": [9, 10, 11, 12, 13],
            "close": [10, 12, 11, 15, 18],
            "adj_close": [10, 12, 11, 15, 18],
            "volume": [100, 110, 120, 130, 140],
        }
    )


def test_add_daily_returns_calculates_simple_returns():
    result = add_daily_returns(_sample_frame())

    assert math.isnan(result.loc[0, "daily_return"])
    assert result.loc[1, "daily_return"] == pytest.approx(0.20)
    assert result.loc[2, "daily_return"] == pytest.approx(-1 / 12)


def test_add_moving_averages_uses_requested_windows():
    result = add_moving_averages(_sample_frame(), windows=[2, 3])

    assert math.isnan(result.loc[0, "sma_2"])
    assert result.loc[1, "sma_2"] == pytest.approx(11.0)
    assert result.loc[2, "sma_3"] == pytest.approx(11.0)


def test_prepare_exploration_frame_sorts_dates_before_calculations():
    frame = _sample_frame().sort_values("date", ascending=False)

    result = prepare_exploration_frame(frame, windows=[2])

    assert result.loc[0, "date"] == pd.Timestamp("2024-01-01")
    assert result.loc[1, "daily_return"] == pytest.approx(0.20)


def test_summarize_exploration_returns_small_numeric_summary():
    explored = prepare_exploration_frame(_sample_frame(), windows=[2])

    summary = summarize_exploration(explored)

    assert summary["rows"] == 5
    assert summary["start_date"] == "2024-01-01"
    assert summary["end_date"] == "2024-01-05"
    assert summary["total_return"] == pytest.approx(0.80)
