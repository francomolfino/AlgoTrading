import pandas as pd
import pytest

from algotrading.data.schema import (
    CANONICAL_COLUMNS,
    ValidationError,
    normalize_ohlcv_dataframe,
    validate_ohlcv_dataframe,
)


def test_normalize_ohlcv_dataframe_uses_canonical_columns_and_sorts_dates():
    raw = pd.DataFrame(
        {
            "Date": ["2024-01-03", "2024-01-02"],
            "Open": [102.0, 100.0],
            "High": [103.0, 101.0],
            "Low": [101.0, 99.0],
            "Close": [102.5, 100.5],
            "Adj Close": [102.0, 100.0],
            "Volume": [1_200_000, 1_000_000],
        }
    )

    normalized = normalize_ohlcv_dataframe(raw)

    assert list(normalized.columns) == CANONICAL_COLUMNS
    assert normalized["date"].tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
    assert normalized["close"].tolist() == [100.5, 102.5]


def test_normalize_fills_adj_close_from_close_when_missing():
    raw = pd.DataFrame(
        {
            "date": ["2024-01-02"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1_000_000],
        }
    )

    normalized = normalize_ohlcv_dataframe(raw)

    assert normalized.loc[0, "adj_close"] == 100.5


def test_validate_raises_when_required_columns_are_missing():
    frame = pd.DataFrame({"date": ["2024-01-02"], "close": [100.0]})

    with pytest.raises(ValidationError, match="open"):
        normalize_ohlcv_dataframe(frame)


def test_validate_raises_when_high_is_below_low():
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "open": [100.0],
            "high": [98.0],
            "low": [99.0],
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1_000_000],
        }
    )

    with pytest.raises(ValidationError, match="high menor que low"):
        validate_ohlcv_dataframe(frame)
